from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database.database import Base


class User(Base):
    """CMS'e giriş yapabilen yerel kullanıcı."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
