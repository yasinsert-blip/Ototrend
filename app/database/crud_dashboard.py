from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import desc, func

from app.database.database import SessionLocal
from app.models.news import News


# ==========================================
# Dashboard Kartları
# ==========================================

def get_news_count():

    db = SessionLocal()

    try:
        return db.query(News).count()

    finally:
        db.close()


def get_source_count():

    db = SessionLocal()

    try:
        return (
            db.query(News.source)
            .distinct()
            .count()
        )

    finally:
        db.close()


def get_ai_pending_count():

    db = SessionLocal()

    try:
        return (
            db.query(News)
            .filter(News.status == "new")
            .count()
        )

    finally:
        db.close()


def get_published_count():

    db = SessionLocal()

    try:
        return (
            db.query(News)
            .filter(News.published == True)
            .count()
        )

    finally:
        db.close()


# ==========================================
# Dropdown Verileri
# ==========================================

def get_sources():

    db = SessionLocal()

    try:

        rows = (
            db.query(News.source)
            .distinct()
            .order_by(News.source)
            .all()
        )

        return [r[0] for r in rows if r[0]]

    finally:
        db.close()


def get_categories():

    db = SessionLocal()

    try:

        rows = (
            db.query(News.category)
            .filter(News.category.isnot(None))
            .distinct()
            .order_by(News.category)
            .all()
        )

        return [r[0] for r in rows if r[0]]

    finally:
        db.close()


# ==========================================
# Son Haberler
# ==========================================

def get_latest_news(limit=10):

    db = SessionLocal()

    try:

        return (
            db.query(News)
            .order_by(desc(News.id))
            .limit(limit)
            .all()
        )

    finally:
        db.close()


# ==========================================
# Son 7 Gün Haber Grafiği
# ==========================================

def get_news_per_day():

    db = SessionLocal()

    try:

        if not hasattr(News, "created_at"):
            return {
                "labels": [],
                "values": [],
            }

        start_date = datetime.now() - timedelta(days=6)

        rows = (
            db.query(
                func.date(News.created_at),
                func.count(News.id)
            )
            .filter(News.created_at >= start_date)
            .group_by(func.date(News.created_at))
            .all()
        )

        counter = defaultdict(int)

        for day, total in rows:
            counter[str(day)] = total

        labels = []
        values = []

        for i in range(7):

            day = (start_date + timedelta(days=i)).date()

            labels.append(day.strftime("%d.%m"))

            values.append(counter.get(str(day), 0))

        return {
            "labels": labels,
            "values": values,
        }

    finally:
        db.close()


# ==========================================
# Kaynak Dağılımı
# ==========================================

def get_source_distribution():

    db = SessionLocal()

    try:

        rows = (
            db.query(
                News.source,
                func.count(News.id)
            )
            .group_by(News.source)
            .order_by(desc(func.count(News.id)))
            .all()
        )

        return {
            "labels": [r[0] for r in rows],
            "values": [r[1] for r in rows],
        }

    finally:
        db.close()


# ==========================================
# Dashboard Özeti
# ==========================================

def get_dashboard_summary():

    return {

        "news_count": get_news_count(),

        "source_count": get_source_count(),

        "pending_count": get_ai_pending_count(),

        "published_count": get_published_count(),

        "sources": get_sources(),

        "categories": get_categories(),

        "news_chart": get_news_per_day(),

        "source_chart": get_source_distribution(),

    }