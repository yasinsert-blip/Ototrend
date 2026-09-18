"""Local suggestions only. Grouping requires an explicit editor POST."""
import re
from datetime import timedelta
from difflib import SequenceMatcher

from app.models.news import News
from app.services.news_selection import title_key, content_skip_reason, UNUSABLE_PARENT_STATUSES


STOP = {"the", "a", "an", "and", "for", "of", "in", "to", "with", "new", "is", "on", "at",
        "ve", "ile", "bir", "için", "yeni", "bu", "da", "de"}


def headline_similarity(first, second):
    """Compare original/available translated titles; no automatic translation."""
    best = 0
    for left in (first.title, first.translated_title):
        for right in (second.title, second.translated_title):
            if not left or not right:
                continue
            a, b = title_key(left, first.source), title_key(right, second.source)
            tokens_a = set(re.findall(r"\w+", a)) - STOP
            tokens_b = set(re.findall(r"\w+", b)) - STOP
            if len(tokens_a & tokens_b) < 3:
                continue
            overlap = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)
            best = max(best, 0.6 * overlap + 0.4 * SequenceMatcher(None, a, b).ratio())
    return best


def suggest_similar(db, news, limit=5):
    if not news.created_at or news.duplicate_of_id:
        return []
    candidates = db.query(News).filter(
        News.id < news.id,  # Older record is always the root; no cycles.
        News.created_at >= news.created_at - timedelta(hours=72),
        News.created_at <= news.created_at + timedelta(hours=72),
        News.duplicate_of_id.is_(None),
        News.status.notin_(UNUSABLE_PARENT_STATUSES),
    ).order_by(News.id.desc()).limit(500).all()
    matches = []
    for candidate in candidates:
        score = headline_similarity(news, candidate)
        if score < 0.55 or content_skip_reason(candidate):
            continue
        warning = ""
        # Numbers may be model names, years or prices. Never silently merge
        # conflicting-looking claims, even if the textual score is high.
        if set(re.findall(r"\d+", news.title or "")) != set(re.findall(r"\d+", candidate.title or "")):
            warning = "Başlıklardaki sayılar farklı: model, yıl veya fiyat değişmiş olabilir."
        matches.append(dict(news=candidate, score=round(score * 100), warning=warning))
    return sorted(matches, key=lambda row: (-row["score"], row["news"].id))[:limit]


def group_confirmed(db, news_id, parent_id):
    # Serialize SQLite checks and writes, preventing concurrent group chains.
    if db.bind.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    rows = db.query(News).filter(News.id.in_([news_id, parent_id])).order_by(News.id).with_for_update().all()
    by_id = {row.id: row for row in rows}
    news, parent = by_id.get(news_id), by_id.get(parent_id)
    if news is None or parent is None:
        raise ValueError("Haber bulunamadı.")
    if parent_id >= news_id:
        raise ValueError("Ana kayıt daha önce eklenmiş bir haber olmalıdır.")
    if news.published or news.status in ("published", "scheduled", "instagram_ready", "deleted", "archived"):
        raise ValueError("Yayın sürecindeki veya arşivlenmiş haber gruplanamaz.")
    if news.duplicate_of_id == parent_id:
        return  # Idempotent confirmation.
    if news.duplicate_of_id or db.query(News.id).filter(News.duplicate_of_id == news_id).first():
        raise ValueError("Mevcut grubu olan haber yeniden bağlanamaz; önce grubu ayırın.")
    if parent_id not in {item["news"].id for item in suggest_similar(db, news)}:
        raise ValueError("Öneri artık geçerli değil. Haberleri yeniden inceleyin.")
    news.duplicate_of_id = parent_id
    news.is_duplicate = True
    # Preserve content, scores, notes, AI output and editorial status.
    db.commit()


def ungroup(db, news_id):
    news = db.get(News, news_id)
    if news is None or news.status == "deleted":
        raise ValueError("Haber bulunamadı.")
    if not news.duplicate_of_id:
        return
    news.duplicate_of_id = None
    news.is_duplicate = False
    if not news.ai_processed and news.status in ("new", "ai_pending", "ai_error"):
        news.status = "editor_review"
        news.ai_next_retry_at = None
    if news.status == "ai_skipped" and (news.ai_last_error or "").startswith(("Aynı başlıklı haber", "İlgili haber")):
        # Return to manual review, not to automatic processing on undo.
        news.status = "editor_review"
        news.ai_last_error = None
    db.commit()
