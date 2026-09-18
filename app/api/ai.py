from fastapi import APIRouter, Request

from app.database.database import SessionLocal
from app.models.source import Source
from app.services.telegram_service import send_telegram_message
from app.security import require_authenticated

router = APIRouter(
    prefix="/api",
    tags=["AI"],
)


@router.post("/test-telegram")
def test_telegram(request: Request):
    require_authenticated(request)

    sent = send_telegram_message("✅ OtoTrend AI Telegram test mesajı")

    return {
        "success": sent,
        "message": (
            "Telegram test mesajı gönderildi."
            if sent
            else "Telegram test mesajı gönderilemedi."
        ),
    }


@router.get("/health")
def health():

    db = SessionLocal()

    try:

        return {
            "status": "ok",
            "database": True,
            "sources": db.query(Source).count(),
        }

    finally:

        db.close()
