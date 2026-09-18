from sqlalchemy.orm import Session
from time import perf_counter

from app.database.database import SessionLocal
from app.models.news import News

from app.ai.pipeline import process
from app.services.fact_check import apply_fact_check
from app.services.ai_timing import start_timing, finish_timing, safe_ai_error
from app.ai.cleaner import clean_text
from app.services.news_selection import select_for_ai, plain_text, content_skip_reason
from app.services.ai_queue_service import review_status_for_importance
BATCH_SIZE = 3

def process_ai_news(news_id: int | None = None):

    db: Session = SessionLocal()

    try:

        # --------------------------------------------------
        # Tek haber AI tekrar üret
        # --------------------------------------------------

        if news_id is not None:

            news = (
                db.query(News)
                .filter(News.id == news_id)
                .first()
            )

            if not news:
                print(f"❌ Haber bulunamadı: {news_id}")
                return

            print(f"🔄 AI yeniden üretiliyor: {news.id}")

            # Reject insufficient source text before clearing any editor/AI work.
            reason = content_skip_reason(news)
            if reason:
                raise ValueError(reason)

            # AI alanlarını sıfırla
            news.ai_processed = False

            news.translated_title = None
            news.summary = None

            news.brand = None
            news.category = None
            news.importance = None
            news.ai_attempts = 0
            news.ai_last_error = None
            news.ai_next_retry_at = None

            # Instagram içeriklerini temizle
            news.instagram_title = None
            news.instagram_caption = None
            news.hashtags = None
            news.image_prompt = None

            # Editör alanlarını sıfırla
            news.status = "ai_pending"
            news.editor_note = None

            db.commit()
            db.refresh(news)

            news_list = [news]

        # --------------------------------------------------
        # Scheduler (eski davranış)
        # --------------------------------------------------

        else:

            news_list = (
                db.query(News)
                .filter(
                    News.ai_processed == False,
                    News.status.in_(["new", "ai_pending", "ai_error"])
                )
                .order_by(News.id.asc())
                .limit(BATCH_SIZE)
                .all()
            )

        print(f"🤖 AI: {len(news_list)} haber işleniyor...")

        for news in news_list:
            run_start = None
            try:

                if not select_for_ai(db, news, check_duplicates=news_id is None):
                    db.commit()
                    continue

                input_text = clean_text(plain_text(news.content))
                start_timing(db, news, input_text)
                run_start = perf_counter()
                result, metrics = process(input_text)
                finish_timing(news, perf_counter() - run_start, metrics)

                if not result:
                    raise ValueError("AI sonucu boş döndü.")

                news.translated_title = result.get("title_tr") or news.title
                news.summary = result.get("summary_tr") or ""
                news.brand = result.get("brand")
                news.category = result.get("category")
                try:
                    news.importance = int(result.get("importance") or 0)
                except (TypeError, ValueError):
                    news.importance = 0
                news.ai_processed = True
                # Editörün bilinçli olarak yeniden işlediği bir haber, puanı
                # ne olursa olsun inceleme için hazır kabul edilir.
                news.status = (
                    "ai_ready"
                    if news_id is not None
                    else review_status_for_importance(news.importance)
                )
                apply_fact_check(news, result)

                db.commit()

                print(f"✅ AI işlendi: {news.id}")

            except Exception as e:

                db.rollback()

                try:

                    news.status = "ai_error"
                    news.ai_processed = False
                    news.ai_last_error = safe_ai_error(e)
                    if run_start is not None:
                        finish_timing(news, perf_counter() - run_start)

                    db.commit()

                except Exception:

                    db.rollback()

                print(f"❌ Haber işlenemedi ({news.id}): {e}")

    finally:

        db.close()
