from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database.database import Base


class NewsImage(Base):
    """Haber için otomatik seçilen görselin kaynak ve lisans kaydı."""

    __tablename__ = "news_images"

    id = Column(Integer, primary_key=True, index=True)
    news_id = Column(Integer, nullable=False, index=True)

    image_url = Column(Text, nullable=False)
    source_url = Column(Text)
    origin = Column(String(40), nullable=False)

    license_name = Column(String(200))
    license_url = Column(Text)
    credit = Column(Text)
    status = Column(String(40), nullable=False, default="review_required")

    is_selected = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
