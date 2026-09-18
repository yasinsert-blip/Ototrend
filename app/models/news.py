from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)

from app.database.database import Base


class News(Base):

    __tablename__ = "news"

    # ==========================
    # Kimlik
    # ==========================

    id = Column(Integer, primary_key=True, index=True)

    # ==========================
    # Kaynak Bilgileri
    # ==========================

    title = Column(Text, nullable=False)

    translated_title = Column(Text)

    summary = Column(Text)

    link = Column(String, unique=True, nullable=False)

    source = Column(String(100), index=True)

    author = Column(String(200))

    image_url = Column(Text)

    language = Column(String(20), default="en")

    # RSS'deki gerçek yayın tarihi
    published_at = Column(DateTime)

    # ==========================
    # AI Alanları
    # ==========================

    ai_model = Column(String(100))

    ai_keywords = Column(Text)

    ai_confidence = Column(
        Integer,
        default=0,
    )

    instagram_title = Column(Text)

    instagram_caption = Column(Text)

    hashtags = Column(Text)

    image_prompt = Column(Text)

    # ==========================
    # İçerik
    # ==========================

    content = Column(Text)

    # ==========================
    # Analiz
    # ==========================

    category = Column(String(100), index=True)

    brand = Column(String(100), index=True)

    importance = Column(Integer, default=0)
    news_value = Column(Integer, nullable=True, index=True)
    news_value_reason = Column(Text)

    sentiment = Column(String(30))

    # ==========================
    # Workflow
    # ==========================

    status = Column(
        String(30),
        default="new",
        index=True,
    )

    ai_processed = Column(
        Boolean,
        default=False,
    )

    # Otomatik AI denemeleri sınırlıdır. Böylece çevrilemeyen tek bir haber
    # arka plandaki işlemci kuyruğunu sürekli meşgul etmez.
    ai_attempts = Column(
        Integer,
        default=0,
        nullable=False,
    )

    ai_last_error = Column(Text)
    fact_check_notes = Column(Text)
    ai_run_started_at = Column(DateTime(timezone=True))
    ai_run_finished_at = Column(DateTime(timezone=True))
    ai_run_seconds = Column(Integer)
    ai_model_seconds = Column(Integer)
    ai_queue_wait_seconds = Column(Integer)
    ai_input_chars = Column(Integer)

    ai_next_retry_at = Column(
        DateTime(timezone=True),
        index=True,
    )

    published = Column(
        Boolean,
        default=False,
    )

    instagram_posted = Column(
        Boolean,
        default=False,
    )

    telegram_sent = Column(
        Boolean,
        default=False,
    )

    # ==========================
    # Editör
    # ==========================

    editor_note = Column(Text)

    # ==========================
    # Görseller
    # ==========================

    thumbnail_url = Column(Text)

    cover_image = Column(Text)

    # ==========================
    # Dashboard
    # ==========================

    featured = Column(
        Boolean,
        default=False,
    )

    views = Column(
        Integer,
        default=0,
    )

    is_duplicate = Column(
        Boolean,
        default=False,
    )
    turkish_telegram_pending = Column(Boolean, nullable=False, default=False)
    telegram_attempts = Column(Integer, nullable=False, default=0)
    telegram_next_retry_at = Column(DateTime(timezone=True))
    telegram_last_error = Column(Text)

    duplicate_of_id = Column(Integer, index=True, nullable=True)

    # ==========================
    # Sistem
    # ==========================

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
