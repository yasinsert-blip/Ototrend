"""Eski yerel veritabanlarını zararsız küçük şema güncellemeleriyle uyumlar."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.database.database import engine


def ensure_database_upgrades() -> None:
    """Alembic çalıştırılmamış mevcut SQLite kurulumlarını da güncel tutar."""
    inspector = inspect(engine)
    with engine.begin() as connection:
        if inspector.has_table("sources"):
            source_columns = {
                column["name"] for column in inspector.get_columns("sources")
            }
            required_source_columns = {
                "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
                "auto_disabled_at": "DATETIME",
            }
            for column_name, definition in required_source_columns.items():
                if column_name not in source_columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE sources ADD COLUMN {column_name} {definition}"
                        )
                    )

        if inspector.has_table("news"):
            news_columns = {column["name"] for column in inspector.get_columns("news")}
            required_news_columns = {
                "ai_attempts": "INTEGER NOT NULL DEFAULT 0",
                "ai_last_error": "TEXT",
                "ai_next_retry_at": "DATETIME",
                "duplicate_of_id": "INTEGER",
                "fact_check_notes": "TEXT",
                "ai_run_started_at": "DATETIME",
                "ai_run_finished_at": "DATETIME",
                "ai_run_seconds": "INTEGER",
                "ai_model_seconds": "INTEGER",
                "ai_queue_wait_seconds": "INTEGER",
                "ai_input_chars": "INTEGER",
                "news_value": "INTEGER",
                "news_value_reason": "TEXT",
                "turkish_telegram_pending": "BOOLEAN NOT NULL DEFAULT 0",
                "telegram_sent": "BOOLEAN NOT NULL DEFAULT 0",
                "telegram_attempts": "INTEGER NOT NULL DEFAULT 0",
                "telegram_next_retry_at": "DATETIME",
                "telegram_last_error": "TEXT",
            }
            for column_name, definition in required_news_columns.items():
                if column_name not in news_columns:
                    connection.execute(
                        text(f"ALTER TABLE news ADD COLUMN {column_name} {definition}")
                    )

            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_news_ai_retry_queue "
                    "ON news (ai_processed, status, ai_next_retry_at, created_at)"
                )
            )

            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_news_duplicate_of_id ON news (duplicate_of_id)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_news_news_value ON news (news_value)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_news_turkish_telegram_queue "
                "ON news (turkish_telegram_pending, telegram_sent, telegram_next_retry_at)"
            ))

            # Eski kayıtlarda yayın durumu yalnızca status alanında tutulmuş
            # olabilir. İki alanı bir kez eşitlemek, eski pano sorgularının da
            # yayınlanan haberleri doğru saymasını sağlar.
            connection.execute(
                text(
                    "UPDATE news SET published = 1 "
                    "WHERE status = 'published' "
                    "AND COALESCE(published, 0) = 0"
                )
            )
