from datetime import UTC, datetime, timedelta
from time import perf_counter

from sqlalchemy import or_, func

from app.ai.logger import AILogger
from app.ai.provider import OLLAMA_MODEL
from app.config import (
    AI_MAX_ATTEMPTS,
    AI_QUEUE_MAX_AGE_HOURS,
    AI_RETRY_DELAY_MINUTES,
    TELEGRAM_NOTIFY_AFTER,
)
from app.ai.stats import (
    add_failure,
    add_success,
    print_summary,
)

from app.database.database import SessionLocal
from app.models.news import News

from app.ai.pipeline import process
from app.services.news_selection import select_for_ai, plain_text
from app.services.fact_check import apply_fact_check
from app.services.ai_timing import start_timing, finish_timing, safe_ai_error
from app.ai.cleaner import clean_text

from app.services.telegram_service import (
    send_telegram_message,
    send_telegram_photo,
)
from app.services.ai_queue_service import (
    ACTIVE_AI_STATUSES,
    refresh_ai_queue,
    review_status_for_importance,
)


def _should_send_telegram(news: News) -> bool:
    """Yalnızca etkinleştirmeden sonra eklenen haberleri bildirir."""
    if (getattr(news, "turkish_telegram_pending", False)
            or getattr(news, "fact_check_notes", None) or news.telegram_sent or not TELEGRAM_NOTIFY_AFTER):
        return False

    try:
        cutoff = datetime.fromisoformat(
            TELEGRAM_NOTIFY_AFTER.replace("Z", "+00:00")
        )
    except ValueError:
        print("⚠️ TELEGRAM_NOTIFY_AFTER geçersiz; Telegram bildirimi atlandı.")
        return False

    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)

    created_at = news.created_at
    if created_at is None:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return created_at >= cutoff


def process_ai_news(limit: int = 1):
    """
    AI tarafından işlenmemiş haberleri işler.
    """

    refresh_ai_queue()
    current_time = datetime.now(UTC)
    queue_cutoff = current_time - timedelta(hours=AI_QUEUE_MAX_AGE_HOURS)

    # ==========================================================
    # İşlenecek Haberleri Bul
    # ==========================================================

    db = SessionLocal()

    try:

        candidates = (

                db.query(News)

                .filter(
                    News.ai_processed == False,
                    News.status.in_(ACTIVE_AI_STATUSES),
                    News.created_at >= queue_cutoff,
                    or_(
                        News.ai_next_retry_at.is_(None),
                        News.ai_next_retry_at <= current_time,
                    ),
                )

                .order_by(func.coalesce(News.news_value, 20).desc(), News.created_at.desc(), News.id.desc())

                .limit(max(100, limit))

                .all()

        )
        news_ids = []
        for row in candidates:
            if len(news_ids) >= max(0, limit):
                break
            if select_for_ai(db, row):
                news_ids.append(row.id)
        db.commit()

    finally:

        db.close()

    # İşlenecek haber yoksa sessizce çık
    if not news_ids:
        return

    print(f"🤖 AI: {len(news_ids)} haber işleniyor...")

    # ==========================================================
    # Haberleri İşle
    # ==========================================================

    for news_id in news_ids:

        db = SessionLocal()

        logger = AILogger()
        news = None
        run_start = None

        logger.set_news(news_id)

        logger.set_model(OLLAMA_MODEL)

        try:

            news = (

                db.query(News)

                .filter(News.id == news_id)

                .first()

            )

            if news is None:

                continue

            if news.ai_processed or news.status not in ACTIVE_AI_STATUSES:
                continue
            if not select_for_ai(db, news):
                db.commit()
                continue

            # ==================================================
            # AI Pipeline
            # ==================================================

            input_text = clean_text(plain_text(news.content))
            start_timing(db, news, input_text)
            run_start = perf_counter()
            result, metrics = process(input_text)
            finish_timing(news, perf_counter() - run_start, metrics)

            logger.set_prompt_size(

                metrics["prompt_kb"]

            )

            logger.set_prompt_time(

                metrics["prompt_time"]

            )

            logger.set_ollama_time(

                metrics["ollama_time"]

            )

            logger.set_parse_time(

                metrics["parse_time"]

            )

            # ==================================================
            # Database Güncelle
            # ==================================================

            news.translated_title = result.get(

                "title_tr"

            )

            news.summary = result.get(

                "summary_tr"

            )

            news.brand = result.get(

                "brand"

            )

            news.category = result.get(

                "category"

            )

            news.importance = result.get("importance")

            news.ai_processed = True
            news.ai_attempts = 0
            news.ai_last_error = None
            news.ai_next_retry_at = None
            news.status = review_status_for_importance(news.importance)
            apply_fact_check(news, result)

            db_start = perf_counter()

            db.commit()

            logger.set_database_time(

                perf_counter() - db_start

            )

            # ==================================================
            # Telegram Mesajı Hazırla
            # ==================================================

            message = (

                f"🚨 OtoTrend AI\n\n"

                f"📰 {news.translated_title}\n\n"

                f"📝 {news.summary}\n\n"

                f"🌍 Kaynak: {news.source}\n\n"

                f"🏷️ Marka: {news.brand}\n"

                f"📂 Kategori: {news.category}\n"

                f"⭐ Önem: {news.importance}/10\n\n"

                f"🔗 {news.link}"

            )

            # ==================================================
            # Telegram Gönder
            # ==================================================

            telegram_start = perf_counter()
            telegram_sent = False

            if _should_send_telegram(news):
                if news.image_url:
                    telegram_sent = send_telegram_photo(
                        news.image_url,
                        message,
                    )
                else:
                    telegram_sent = send_telegram_message(message)

                if telegram_sent:
                    news.telegram_sent = True
                    db.commit()
            else:
                print("ℹ️ Telegram atlandı: haber bildirim başlangıcından önce eklenmiş.")

            logger.set_telegram_time(
                perf_counter() - telegram_start
            )

            # ==================================================
            # Logger
            # ==================================================

            logger.finish()

            logger.print()

            # ==================================================
            # Statistics
            # ==================================================

            add_success(
                model=OLLAMA_MODEL,
                prompt_kb=metrics["prompt_kb"],
                response_kb=metrics["response_kb"],
                duration=logger.total_time,
            )

            print(
                f"✅ AI işlendi: {news.title}"
            )

        except Exception as e:

            db.rollback()

            add_failure()

            if news is not None:
                attempts = int(news.ai_attempts or 0) + 1
                news.ai_attempts = attempts
                news.ai_last_error = safe_ai_error(e)
                if run_start is not None:
                    finish_timing(news, perf_counter() - run_start)
                news.updated_at = datetime.now(UTC)

                if attempts >= AI_MAX_ATTEMPTS:
                    news.status = "ai_failed"
                    news.ai_next_retry_at = None
                    print(
                        "ℹ️ AI otomatik deneme sınırına ulaştı: "
                        f"haber #{news_id} editörün manuel incelemesine bırakıldı."
                    )
                else:
                    delay_minutes = AI_RETRY_DELAY_MINUTES * (2 ** (attempts - 1))
                    news.status = "ai_error"
                    news.ai_next_retry_at = datetime.now(UTC) + timedelta(
                        minutes=delay_minutes
                    )
                    print(
                        "ℹ️ AI yeniden deneme planlandı: "
                        f"haber #{news_id}, {delay_minutes} dakika sonra."
                    )

                try:
                    db.commit()
                except Exception:
                    db.rollback()

            print()

            print("❌ AI Worker Hatası")

            print(f"📰 Haber ID : {news_id}")

            print(f"⚠️ {e}")

            print()

        finally:

            db.close()

    # ==========================================================
    # Final Statistics
    # ==========================================================

    print_summary()

    print()

    print("🤖 AI Worker tamamlandı.")

    print()
