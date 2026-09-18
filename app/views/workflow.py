"""Sol menüdeki yayın iş akışı sayfaları."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, or_

from app.config import AI_PROVIDER, OLLAMA_MODEL, RUN_SCHEDULER
from app.database.database import SessionLocal
from app.models.news import News
from app.models.source import Source
from app.services.dashboard_service import get_dashboard_stats


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
GENERATED_INSTAGRAM_DIR = Path("app/static/generated/instagram")


def _require_auth(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _render_workflow(
    request: Request,
    *,
    page_title: str,
    subtitle: str,
    page_mode: str,
    statuses: tuple[str, ...] = (),
):
    auth = _require_auth(request)
    if auth:
        return auth

    db = SessionLocal()
    try:
        stats = get_dashboard_stats(db)
        query = (
            db.query(News)
            .filter(or_(News.status.is_(None), News.status != "deleted"))
            .order_by(desc(News.created_at))
        )
        if statuses:
            query = query.filter(News.status.in_(statuses))

        news = query.limit(100).all()
        telegram_sent = db.query(News).filter(News.telegram_sent.is_(True)).count()
        source_total = db.query(Source).count()
    finally:
        db.close()

    images = []
    if page_mode == "images" and GENERATED_INSTAGRAM_DIR.exists():
        for image_path in sorted(
            GENERATED_INSTAGRAM_DIR.glob("*.jpg"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            images.append(
                {
                    "name": image_path.name,
                    "url": f"/static/generated/instagram/{image_path.name}",
                }
            )

    runtime_settings = {
        "Yapay zekâ sağlayıcısı": "Yerel Ollama" if AI_PROVIDER == "ollama" else AI_PROVIDER,
        "Yerel model": OLLAMA_MODEL if AI_PROVIDER != "openai" else "OpenAI modeli",
        "Arka plan taraması": "Açık" if RUN_SCHEDULER else "Kapalı",
        "Tanımlı kaynak": str(source_total),
        "Telegram bağlantısı": "Yapılandırıldı",
    }

    return templates.TemplateResponse(
        request=request,
        name="workflow.html",
        context={
            "request": request,
            "page_title": page_title,
            "subtitle": subtitle,
            "page_mode": page_mode,
            "news": news,
            "stats": stats,
            "images": images,
            "telegram_sent": telegram_sent,
            "runtime_settings": runtime_settings,
        },
    )


@router.get("/ai")
def ai_editor(request: Request):
    auth = _require_auth(request)
    if auth:
        return auth
    return RedirectResponse(url="/editor?status=ai_pending", status_code=303)


@router.get("/images")
def images_page(request: Request):
    return _render_workflow(
        request,
        page_title="AI Görseller",
        subtitle="Kaynak fotoğrafı ve OtoTrendTR görsel anayasasıyla oluşturulan Instagram görselleri.",
        page_mode="images",
    )


@router.get("/instagram")
def instagram_page(request: Request):
    return _render_workflow(
        request,
        page_title="Instagram Kuyruğu",
        subtitle="AI hazır haberleri dönüştürün; taslakları açın, metin ve görseli kontrol edip yayın için hazırlayın.",
        page_mode="instagram",
        statuses=("ai_ready", "editor_review", "instagram_draft", "instagram_ready"),
    )


@router.get("/telegram")
def telegram_page(request: Request):
    return _render_workflow(
        request,
        page_title="Telegram",
        subtitle="Telegram'a gönderime uygun ve gönderilmiş haber kayıtlarını takip edin.",
        page_mode="telegram",
        statuses=("scheduled", "published"),
    )


@router.get("/scheduler")
def scheduler_page(request: Request):
    return _render_workflow(
        request,
        page_title="Yayın Planı",
        subtitle="Planlanan içerikleri tek listede gözden geçirin.",
        page_mode="scheduler",
        statuses=("scheduled",),
    )


@router.get("/analytics")
def analytics_page(request: Request):
    return _render_workflow(
        request,
        page_title="Analitik",
        subtitle="Haber, kaynak ve editöryal süreç durumlarının canlı özeti.",
        page_mode="analytics",
    )


@router.get("/settings")
def settings_page(request: Request):
    return _render_workflow(
        request,
        page_title="Ayarlar",
        subtitle="Uygulamanın güvenli çalışma durumunu kontrol edin.",
        page_mode="settings",
    )


@router.get("/profile")
def profile_page(request: Request):
    return _render_workflow(
        request,
        page_title="Profil",
        subtitle="Oturum ve rol bilgileri.",
        page_mode="profile",
    )
