from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)

from app.database.database import Base


class Source(Base):

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)

    # ==========================
    # Temel Bilgiler
    # ==========================

    name = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    website = Column(Text)

    rss_url = Column(Text)

    scraper = Column(
        String(50),
        default="rss",
    )

    language = Column(
        String(20),
        default="en",
    )

    country = Column(
        String(50),
        default="Global",
    )

    # ==========================
    # Sprint 15.1
    # Kaynak Tipi
    # ==========================

    source_type = Column(
        String(30),
        default="editorial",
        nullable=False,
    )

    brand = Column(
        String(100),
    )

    is_oem = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ==========================
    # Yönetim
    # ==========================

    enabled = Column(
        Boolean,
        default=True,
    )

    priority = Column(
        Integer,
        default=1,
    )

    # ==========================
    # İstatistik
    # ==========================

    total_news = Column(
        Integer,
        default=0,
    )

    success_count = Column(
        Integer,
        default=0,
    )

    error_count = Column(
        Integer,
        default=0,
    )

    last_run = Column(DateTime)

    last_success = Column(DateTime)

    last_error = Column(Text)

    # Kaynak sağlığı: yalnızca peş peşe gelen hatalar otomatik durdurmaya
    # neden olur. Başarılı bir tarama bu sayacı sıfırlar.
    consecutive_failures = Column(
        Integer,
        default=0,
        nullable=False,
    )

    auto_disabled_at = Column(DateTime)

    # ==========================
    # Sistem
    # ==========================

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
