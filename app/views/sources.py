"""Kaynak arama, durum yönetimi ve doğrulamalı düzenleme ekranları."""

from types import SimpleNamespace
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError

from app.scrapers.registry import list_scrapers
from app.services.source_service import (
    list_sources, get_source_by_id, create_new_source, update_existing_source,
    remove_source, get_enabled_sources, enable_existing_source,
    disable_existing_source,
)
from app.services.source_health import summarize_source_health
from app.services.source_validator import validate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def check_auth(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _back_to_sources(request, message, level="success"):
    request.session["source_feedback"] = {"message": message, "level": level}
    query = urlencode({
        key: request.query_params[key] for key in ("q", "state")
        if request.query_params.get(key)
    })
    return RedirectResponse(url="/sources" + ("?" + query if query else ""), status_code=303)


def _source_form(request, source=None, *, values=None, error=None):
    names = list_scrapers()
    names = (["RSS"] if "RSS" in names else []) + [name for name in names if name != "RSS"]
    if source is None and values is None:
        values = dict(name="", rss_url="", website="", scraper="RSS", priority=1, enabled=True)
    return templates.TemplateResponse(
        request=request, name="sources/edit.html" if source else "sources/form.html",
        context={
            "request": request, "source": source,
            "values": SimpleNamespace(**values) if values is not None else source,
            "scrapers": names, "error": error,
        },
        status_code=422 if error else 200,
    )


@router.get("/sources")
def sources_page(request: Request, q: str = "", state: str = ""):
    auth = check_auth(request)
    if auth:
        return auth
    sources = list_sources()
    issues = {source.id: validate(source) for source in sources}
    attention = lambda source: bool(issues[source.id] or source.consecutive_failures)
    health = summarize_source_health(sources)
    health["needs_attention"] = sum(attention(source) for source in sources)
    health["inactive"] = sum(not source.enabled for source in sources)
    predicates = {
        "active": lambda source: source.enabled,
        "inactive": lambda source: not source.enabled,
        "attention": attention,
        "auto_disabled": lambda source: not source.enabled and source.auto_disabled_at is not None,
    }
    if state in predicates:
        sources = [source for source in sources if predicates[state](source)]
    keyword = q.strip().casefold()
    if keyword:
        sources = [
            source for source in sources
            if keyword in " ".join(str(value or "") for value in (
                source.name, source.website, source.rss_url, source.brand
            )).casefold()
        ]
    return templates.TemplateResponse(
        request=request, name="sources/list.html",
        context={
            "request": request, "sources": sources, "health": health,
            "source_issues": issues, "q": q, "state": state,
            "feedback": request.session.pop("source_feedback", None),
            "filter_query": urlencode({"q": q, "state": state}),
        },
    )


@router.get("/sources/new")
def new_source_page(request: Request):
    return check_auth(request) or _source_form(request)


@router.post("/sources/new")
def create_source_page(
    request: Request, name: str = Form(""), rss_url: str = Form(""),
    website: str = Form(""), scraper: str = Form("RSS"),
    priority: int = Form(1), enabled: str | None = Form(None),
):
    auth = check_auth(request)
    if auth:
        return auth
    values = dict(name=name, rss_url=rss_url, website=website, scraper=scraper,
                  priority=priority, enabled=enabled is not None)
    try:
        create_new_source(**values)
    except (ValueError, IntegrityError) as exc:
        error = str(exc) if isinstance(exc, ValueError) else "Bu kaynak adı zaten kullanılıyor."
        return _source_form(request, values=values, error=error)
    return _back_to_sources(request, "Kaynak eklendi.")


@router.get("/sources/{source_id}/edit")
def edit_source_page(request: Request, source_id: int):
    auth = check_auth(request)
    if auth:
        return auth
    source = get_source_by_id(source_id)
    if source is None:
        return _back_to_sources(request, "Kaynak bulunamadı.", "warning")
    return _source_form(request, source)


@router.post("/sources/{source_id}/edit")
def edit_source(
    request: Request, source_id: int, name: str = Form(""),
    rss_url: str = Form(""), website: str = Form(""), scraper: str = Form("RSS"),
    priority: int = Form(1), enabled: str | None = Form(None),
):
    auth = check_auth(request)
    if auth:
        return auth
    source = get_source_by_id(source_id)
    if source is None:
        return _back_to_sources(request, "Kaynak bulunamadı.", "warning")
    values = dict(name=name, rss_url=rss_url, website=website, scraper=scraper,
                  priority=priority, enabled=enabled is not None)
    try:
        update_existing_source(source_id=source_id, **values)
    except (ValueError, IntegrityError) as exc:
        error = str(exc) if isinstance(exc, ValueError) else "Bu kaynak adı zaten kullanılıyor."
        return _source_form(request, source, values=values, error=error)
    return _back_to_sources(request, "Kaynak güncellendi.")


@router.post("/sources/{source_id}/delete")
def delete_source_page(request: Request, source_id: int):
    auth = check_auth(request)
    if auth:
        return auth
    removed = remove_source(source_id)
    return _back_to_sources(request, "Kaynak silindi. Haber geçmişi korundu." if removed else "Kaynak bulunamadı.")


@router.post("/sources/{source_id}/enable")
def enable_source_page(request: Request, source_id: int):
    auth = check_auth(request)
    if auth:
        return auth
    try:
        source = enable_existing_source(source_id)
    except ValueError as exc:
        return _back_to_sources(request, str(exc), "warning")
    return _back_to_sources(request, "Kaynak etkinleştirildi." if source else "Kaynak bulunamadı.")


@router.post("/sources/{source_id}/disable")
def disable_source_page(request: Request, source_id: int):
    auth = check_auth(request)
    if auth:
        return auth
    source = disable_existing_source(source_id)
    return _back_to_sources(request, "Kaynak duraklatıldı; sonraki taramalara alınmayacak." if source else "Kaynak bulunamadı.")


@router.get("/test-enabled-sources")
def test_enabled_sources(request: Request):
    auth = check_auth(request)
    if auth:
        return auth
    return [
        dict(id=source.id, name=source.name, scraper=source.scraper,
             priority=source.priority, enabled=source.enabled)
        for source in get_enabled_sources()
    ]
