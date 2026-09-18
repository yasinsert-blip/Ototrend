"""Local, conservative selection; never deletes articles or calls a model."""
import re
import unicodedata
from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup

from app.models.news import News

UNUSABLE_PARENT_STATUSES = ("deleted", "archived", "ai_failed", "ai_skipped")


def plain_text(value):
    soup = BeautifulSoup(value or "", "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def title_key(title, source=""):
    text = unicodedata.normalize("NFKC", plain_text(title)).casefold()
    # Only strip the known publisher suffix, never arbitrary headline clauses.
    publisher = (source or "").split(" (")[0].casefold()
    if publisher == "reuters otomotiv":
        publisher = "reuters"
    if publisher:
        text = re.sub(r"\s+[-–—|]\s*" + re.escape(publisher) + r"$", "", text)
    return " ".join(text.split())


def content_skip_reason(news):
    body = plain_text(news.content)
    words = re.findall(r"\w+", body.casefold())
    title_words = set(re.findall(r"\w+", plain_text(news.title).casefold()))
    if len(body) < 250 or len(words) < 40 or len(set(words) - title_words) < 12:
        return "Yeterli kaynak metni yok; yalnızca başlıktan AI üretimi yapılmadı."
    return None


def find_duplicate(db, news):
    key = title_key(news.title, news.source)
    if len(key) < 35 or len(key.split()) < 6:
        return None
    reference = news.created_at or datetime.now(UTC)
    candidates = db.query(News).filter(
        News.created_at >= reference - timedelta(hours=48),
        News.created_at <= reference,
        News.duplicate_of_id.is_(None),
        News.status.notin_(UNUSABLE_PARENT_STATUSES),
    )
    if news.id is not None:
        candidates = candidates.filter(News.id < news.id)
    for candidate in candidates.order_by(News.id.desc()).limit(2000):
        if title_key(candidate.title, candidate.source) != key:
            continue
        # A headline-only item must not suppress a later, usable article.
        if not content_skip_reason(candidate):
            return candidate
    return None


def select_for_ai(db, news, *, check_duplicates=True):
    """Return False and keep an explanation on skipped, unprocessed rows."""
    parent = db.get(News, news.duplicate_of_id) if news.duplicate_of_id else None
    if parent is not None and (
        parent.status in UNUSABLE_PARENT_STATUSES or content_skip_reason(parent)
    ):
        parent = None
    if check_duplicates and parent is None:
        news.duplicate_of_id = None
        news.is_duplicate = False
    if check_duplicates and parent is None:
        parent = find_duplicate(db, news)
    reason = content_skip_reason(news)
    if check_duplicates and parent is not None:
        news.is_duplicate = True
        news.duplicate_of_id = parent.id
        reason = f"İlgili haber #{parent.id} altında gruplandı; tekrar AI işlemi yapılmadı."
    if reason:
        news.status = "ai_skipped"
        news.ai_last_error = reason
        news.ai_next_retry_at = None
        return False
    if news.ai_last_error and news.ai_last_error.startswith(("Yeterli kaynak metni", "Aynı başlıklı haber", "İlgili haber")):
        news.ai_last_error = None
    return True
