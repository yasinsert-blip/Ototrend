from fastapi import APIRouter, BackgroundTasks, Request, status

from app.database.database import SessionLocal
from app.services.dashboard_service import get_dashboard_stats
from app.services.news_service import update_news
from app.security import require_authenticated

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard API"],
)

@router.get("/stats")
def dashboard_stats(request: Request):
    """
    Dashboard KPI verileri
    """

    require_authenticated(request)

    db = SessionLocal()

    try:
        return get_dashboard_stats(db)

    finally:
        db.close()


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_news(request: Request, background_tasks: BackgroundTasks):
    require_authenticated(request)
    background_tasks.add_task(update_news)
    return {"status": "started"}
