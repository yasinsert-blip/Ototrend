"""Add the September 2026 source shortlist, without altering existing sources.

Default: read-only preview plus live feed checks. --apply adds missing sources
and imports their first 10 feed items through the normal deduplicating store.
No scheduler, AI generation, messages, or publishing are invoked here.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from app.database.database import SessionLocal
from app.database.crud import save_news
from app.database.source_crud import mark_source_run, mark_source_success, mark_source_error
from app.models.source import Source
from app.scrapers.rss.common import read_rss
from app.services.source_validator import validate

SHORTLIST = [
    dict(name="Electrive", website="https://www.electrive.com/", rss_url="https://www.electrive.com/feed/", priority=1),
    dict(name="Just Auto", website="https://www.just-auto.com/", rss_url="https://www.just-auto.com/feed/", priority=1),
    dict(name="Automotive World", website="https://www.automotiveworld.com/", rss_url="https://www.automotiveworld.com/feed/", priority=1),
    dict(name="WardsAuto", website="https://www.wardsauto.com/", rss_url="https://www.wardsauto.com/feeds/news/", priority=2),
    dict(name="Charged EVs", website="https://chargedevs.com/", rss_url="https://chargedevs.com/feed/", priority=2),
    # User-approved headline discovery, not an official Reuters RSS/full-text feed.
    dict(name="Reuters Otomotiv (Google Haberler)",
         website="https://www.reuters.com/business/autos-transportation/",
         rss_url="https://news.google.com/rss/search?q=site%3Areuters.com+%28automaker+OR+automotive+OR+cars+OR+vehicles+OR+EV%29+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen",
         priority=1),
]


def host(url):
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


def existing_match(candidate, sources):
    return next((source for source in sources if
                 source.name.casefold() == candidate["name"].casefold()
                 or host(source.website) == host(candidate["website"])
                 or (source.rss_url or "").rstrip("/") == candidate["rss_url"].rstrip("/")), None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        existing = db.query(Source).all()
    candidates = [row for row in SHORTLIST if existing_match(row, existing) is None]
    if not candidates:
        print("All shortlisted sources already exist; nothing changed.")
        return
    fetched = {}
    for values in candidates:
        source = Source(**values, scraper="RSS", enabled=True)
        errors = validate(source)
        if errors:
            raise ValueError(errors)
        news = read_rss(values["rss_url"], values["name"], limit=10, raise_on_error=True)
        if not news or any(not row.get("title") or urlsplit(row.get("link") or "").scheme not in {"http", "https"} for row in news):
            raise ValueError(f"Invalid or empty feed: {values['name']}")
        fetched[values["name"]] = news
    if not args.apply:
        print(json.dumps(dict(planned=candidates, verified_items={name: len(rows) for name, rows in fetched.items()}), ensure_ascii=False, indent=2))
        return
    output = ROOT / "logs/source-discovery"
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    audit = dict(created_at=stamp, added=[], imports=[])
    with SessionLocal() as db:
        current = db.query(Source).all()
        snapshot = [dict(id=row.id, name=row.name, website=row.website, rss_url=row.rss_url,
                         scraper=row.scraper, enabled=row.enabled, priority=row.priority) for row in current]
        (output / f"sources-before-{stamp}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        added = []
        for values in candidates:
            if existing_match(values, current):
                continue
            source = Source(**values, scraper="RSS", enabled=True, language="en", country="Global", source_type="editorial", is_oem=False)
            db.add(source)
            current.append(source)
            added.append(source)
        db.flush()
        audit["added"] = [dict(id=row.id, name=row.name, rss_url=row.rss_url) for row in added]
        db.commit()
    audit_path = output / f"added-{stamp}.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    for source in audit["added"]:
        name = source["name"]
        mark_source_run(name)
        try:
            news = save_news(fetched[name])
            mark_source_success(name, len(news))
            audit["imports"].append(dict(name=name, fetched=len(fetched[name]), added=len(news), news_ids=[row.id for row in news]))
        except Exception as error:
            mark_source_error(name, str(error))
            audit["imports"].append(dict(name=name, error=str(error)))
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
