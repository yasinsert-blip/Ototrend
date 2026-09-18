from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.services.news_service import update_news
from app.services.ai_worker import process_ai_news
from app.services.retention_service import run_news_retention
from app.services.turkish_telegram import deliver_turkish_notifications
from app.config import (
    AI_BATCH_SIZE,
    AI_WORKER_INTERVAL_SECONDS,
    NEWS_SCAN_INTERVAL_MINUTES,
)


scheduler = BackgroundScheduler()


def start_scheduler():

    if scheduler.running:
        return


    # ==========================================================
    # RSS Haber Toplama
    # ==========================================================

    scheduler.add_job(
        update_news,
        "interval",
        minutes=NEWS_SCAN_INTERVAL_MINUTES,
        id="news_job",
        replace_existing=True,
        next_run_time=datetime.now(),
        coalesce=True,
        max_instances=1,
        misfire_grace_time=NEWS_SCAN_INTERVAL_MINUTES * 60,
    )


    # ==========================================================
    # AI Worker
    # ==========================================================

    scheduler.add_job(
        process_ai_news,
        "interval",
        seconds=AI_WORKER_INTERVAL_SECONDS,
        kwargs={"limit": AI_BATCH_SIZE},
        id="ai_job",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=AI_WORKER_INTERVAL_SECONDS,
    )


    # ==========================================================
    # Haber arşivleme ve yedekli temizlik
    # ==========================================================

    scheduler.add_job(
        run_news_retention,
        "cron",
        hour=3,
        minute=15,
        id="news_retention_job",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60 * 6,
    )


    scheduler.add_job(
        deliver_turkish_notifications,
        "interval", seconds=60,
        id="turkish_telegram_job", replace_existing=True,
        next_run_time=datetime.now(), coalesce=True, max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.start()


    print("⏰ Scheduler başlatıldı.")
    print(f"   📰 RSS Worker : {NEWS_SCAN_INTERVAL_MINUTES} dakikada bir")
    print(
        "   🤖 AI Worker  : "
        f"{AI_WORKER_INTERVAL_SECONDS} saniyede bir ({AI_BATCH_SIZE} haber)"
    )
    print("   🗄️ Haber arşivi : her gün 03:15")


def stop_scheduler():
    if scheduler.running:
        import os
        scheduler.shutdown(wait=os.getenv('APP_ENV') == 'desktop')
        print("Scheduler durduruldu.")
