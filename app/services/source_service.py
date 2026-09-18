from app.database.database import SessionLocal
from app.models.source import Source
from types import SimpleNamespace
from app.services.source_validator import validate

from app.database.source_crud import (
    get_all_sources,
    get_source,
    create_source,
    update_source,
    delete_source,
    enable_source,
    disable_source,
)


def get_enabled_sources():

    db = SessionLocal()

    try:

        sources = (
            db.query(Source)
            .filter(Source.enabled == True)
            .order_by(Source.priority, Source.id)
            .all()
        )

        return sources

    finally:

        db.close()


def list_sources():
    return get_all_sources()


def get_source_by_id(source_id: int):
    return get_source(source_id)


def create_new_source(
    name: str,
    rss_url: str,
    website: str,
    scraper: str,
    priority: int = 1,
    enabled: bool = True,
):
    values = _validated_values(name, rss_url, website, scraper, priority)
    return create_source(
        **values, enabled=enabled, fail_if_exists=True,
    )


def update_existing_source(
    source_id: int,
    name: str,
    rss_url: str,
    website: str,
    scraper: str,
    enabled: bool,
    priority: int,
):
    values = _validated_values(name, rss_url, website, scraper, priority)
    return update_source(
        source_id=source_id,
        **values,
        enabled=enabled,
    )


def remove_source(source_id: int):
    return delete_source(source_id)


def enable_existing_source(source_id: int):
    source = get_source(source_id)
    if source is None:
        return None
    errors = validate(source)
    if errors:
        raise ValueError(" ".join(errors))
    return enable_source(source_id)


def disable_existing_source(source_id: int):
    return disable_source(source_id)


def _validated_values(name, rss_url, website, scraper, priority):
    values = dict(
        name=name.strip(), rss_url=rss_url.strip(), website=website.strip(),
        scraper="RSS" if scraper.strip().lower() == "rss" else scraper.strip(),
        priority=priority,
    )
    errors = validate(SimpleNamespace(**values))
    if errors:
        raise ValueError(" ".join(errors))
    return values
