from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.database.crud import get_categories, get_news, get_sources
from app.services.dashboard_service import get_dashboard_stats
from app.services.news_service import update_news

router = APIRouter()

STATUS_OPTIONS = (
    ("new", "Yeni"),
    ("ai_pending", "AI bekliyor"),
    ("ai_processed", "AI işlendi"),
    ("ai_skipped", "AI atlandı"),
    ("ai_failed", "AI manuel kontrol"),
    ("ai_ready", "AI hazır"),
    ("editor_review", "Editör incelemesi"),
    ("instagram_draft", "Instagram taslağı"),
    ("instagram_ready", "Instagram hazır"),
    ("scheduled", "Planlandı"),
    ("published", "Yayınlandı"),
    ("archived", "Arşivlendi"),
    ("ai_error", "AI hatası"),
)

templates = Jinja2Templates(
    directory="app/templates"
)


@router.post("/dashboard/refresh")
def refresh_dashboard_news(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Dashboard'dan kaynak taramasını başlatıp kullanıcıyı geri döndürür."""
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=303)

    background_tasks.add_task(update_news)
    return RedirectResponse(
        url="/dashboard?refresh=started",
        status_code=303,
    )


@router.get("/")
@router.get("/dashboard")
def home(
    request: Request,
    q: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
):
    """
    Dashboard Ana Sayfası
    """

    # ==========================================================
    # Authentication
    # ==========================================================

    if not request.session.get("authenticated"):

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    # ==========================================================
    # News List
    # ==========================================================

    news_result = get_news(
        keyword=q,
        source=source,
        category=category,
        status=status,
        page=page,
        page_size=20,
    )

    # ==========================================================
    # Dashboard Stats
    # ==========================================================

    db = SessionLocal()

    try:

        stats = get_dashboard_stats(db)

    finally:

        db.close()

    # ==========================================================
    # Template Context
    # ==========================================================

    context = {

        "request": request,

        # News

        "news": news_result["items"],
        "count": news_result["total"],

        "page": news_result["page"],
        "page_size": news_result["page_size"],
        "total_pages": news_result["total_pages"],
        "page_numbers": list(
            range(
                max(1, news_result["page"] - 2),
                min(news_result["total_pages"], news_result["page"] + 2) + 1,
            )
        ),

        # Filters

        "q": q or "",
        "source": source or "",
        "category": category or "",
        "status": status or "",
        "sources": get_sources(),
        "categories": get_categories(),
        "status_options": STATUS_OPTIONS,
        "filters_active": any((q, source, category, status)),
        "filter_query": urlencode(
            {
                key: value
                for key, value in {
                    "q": q,
                    "source": source,
                    "category": category,
                    "status": status,
                }.items()
                if value
            }
        ),

        # Dashboard

        "stats": stats,
        **stats,
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context,
    )
