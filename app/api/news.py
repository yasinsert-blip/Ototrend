from typing import Optional

from fastapi import APIRouter, Query, Request

from app.database.crud import get_news, get_news_by_id
from app.security import require_authenticated

router = APIRouter(
    prefix="/api/news",
    tags=["News"],
)


@router.get("/")
def list_news(
    request: Request,
    keyword: Optional[str] = None,
    source: Optional[str] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    require_authenticated(request)
    return get_news(
        keyword=keyword,
        source=source,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get("/{news_id}")
def news_detail(request: Request, news_id: int):
    require_authenticated(request)
    return get_news_by_id(news_id)
