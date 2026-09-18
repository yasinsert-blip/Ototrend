from fastapi import APIRouter, Request
from app.database.source_crud import get_all_sources
from app.security import require_authenticated

router = APIRouter(
    prefix="/sources",
    tags=["Sources"],
)


@router.get("/")
def list_sources(request: Request):
    require_authenticated(request)
    sources = get_all_sources()

    return [
        {
            "id": s.id,
            "name": s.name,
            "website": s.website,
            "rss_url": s.rss_url,
            "enabled": s.enabled,
            "priority": s.priority,
            "total_news": s.total_news,
            "error_count": s.error_count,
        }
        for s in sources
    ]
