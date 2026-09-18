"""Explainable editorial ranking, separate from AI importance and fact checks."""
import re
import unicodedata
from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup


def clean(value):
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    return unicodedata.normalize("NFKC", text).casefold().replace("ı", "i").replace("i\u0307", "i")


def matches(text, words):
    return any(re.search(
        r"(?<!\w)" + re.escape(unicodedata.normalize("NFKC", word).casefold().replace("ı", "i").replace("i\u0307", "i")) + r"(?!\w)", text
    ) for word in words)


def evaluate_news_value(title, content=""):
    headline = clean(title)
    # Ignore footer/navigation material; promotions are identified from headline
    # only so a news article mentioning an advertising campaign is not penalized.
    text = headline + " " + clean(content)[:2000]
    score, reasons = 20, []
    automotive = matches(text, (
        "otomobil", "otomotiv", "araç", "elektrikli", "şarj", "batarya", "car", "cars",
        "vehicle", "vehicles", "automotive", "automaker", "ev", "suv", "battery",
        "charging", "togg", "toyota", "ford", "bmw", "audi", "tesla", "byd", "volkswagen",
        "renault", "dacia", "hyundai", "kia", "nissan", "stellantis", "polestar", "volvo",
    ))
    if automotive:
        score += 15
        reasons.append("Otomotiv bağlantısı +15")
        if matches(text, ("türkiye", "turkiye", "turkey", "turkish", "türk", "togg", "ötv")):
            score += 25
            reasons.append("Türkiye bağlantısı +25")
        for terms, points, label in (
            (("fiyat", "fiyatı", "fiyatları", "fiyat listesi", "price", "prices", "pricing", "ötv"), 15, "Fiyat/vergi bilgisi"),
            (("yeni model", "tanıtıldı", "tanitti", "new model", "unveils", "reveals", "debut", "launch"), 10, "Yeni model/tanıtım"),
            (("yatırım", "yatirim", "fabrika", "üretim", "investment", "factory", "production", "plant"), 15, "Yatırım/üretim"),
            (("geri çağırma", "geri çağrıldı", "recall", "recalls", "regulation", "düzenleme", "tariff", "tariffs", "sales", "satış"), 15, "Güvenlik/sektör gelişmesi"),
        ):
            if matches(text, terms):
                score += points
                reasons.append(f"{label} +{points}")
    if matches(headline, ("webinar", "web semineri", "register now", "hemen kaydol", "sponsored", "sponsorlu", "advertorial", "reklam içeriği")):
        score -= 60
        reasons.append("Tanıtım/webinar işareti −60")
    if not automotive and matches(headline, ("horoscope", "burç", "football", "futbol", "recipe", "yemek tarifi", "soybean", "soya", "cargo plane", "kargo uçağı")):
        score -= 20
        reasons.append("Otomotiv dışı konu işareti −20")
    return max(0, min(100, score)), "; ".join(["Başlangıç 20"] + reasons)


def score_news(news):
    news.news_value, news.news_value_reason = evaluate_news_value(news.title, news.content)


def score_recent_unrated(db, now=None):
    """Bounded metadata-only backfill; never changes editorial status/content."""
    from app.models.news import News
    cutoff = (now or datetime.now(UTC)) - timedelta(hours=48)
    rows = db.query(News).filter(
        News.news_value.is_(None), News.created_at >= cutoff,
        News.status != "deleted",
    ).order_by(News.id.desc()).limit(2000).all()
    for row in rows:
        score_news(row)
    return len(rows)
