"""Uzun süren Instagram taslak üretimi için hafif iş kuyruğu.

Yerel Ollama aynı anda birden fazla üretim aldığında bilgisayarı gereksiz yere
zorlar. Bu yüzden işler tek sırada çalışır; tarayıcı ise ilerleme bilgisini
düzenli aralıklarla sorgular.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock
from uuid import uuid4

from app.services.instagram_draft_service import (
    InstagramDraftError,
    create_instagram_draft,
)


_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="instagram-draft",
)
_jobs: dict[str, dict] = {}
_lock = Lock()
_JOB_MAX_AGE = timedelta(hours=2)


def _now() -> datetime:
    return datetime.now()


def _public_job(job: dict) -> dict:
    """Tarayıcıya yalnızca gerekli, güvenli iş bilgisini döndürür."""
    return {
        "id": job["id"],
        "news_id": job["news_id"],
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "result": job.get("result"),
    }


def _remove_expired_jobs() -> None:
    threshold = _now() - _JOB_MAX_AGE
    stale_ids = [
        job_id
        for job_id, job in _jobs.items()
        if job["updated_at"] < threshold
        and job["status"] in {"completed", "failed"}
    ]
    for job_id in stale_ids:
        _jobs.pop(job_id, None)


def _update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result: dict | None = None,
) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        if status is not None:
            job["status"] = status
        if progress is not None:
            job["progress"] = max(0, min(100, progress))
        if message is not None:
            job["message"] = message
        if result is not None:
            job["result"] = result
        job["updated_at"] = _now()


def _run_job(job_id: str, news_id: int) -> None:
    _update_job(
        job_id,
        status="running",
        progress=8,
        message="İşlem başlatılıyor.",
    )

    try:
        draft = create_instagram_draft(
            news_id,
            report_progress=lambda percent, message: _update_job(
                job_id,
                progress=percent,
                message=message,
            ),
        )
    except (InstagramDraftError, LookupError, ValueError) as exc:
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 - hata kullanıcıya güvenli iletilir.
        print(f"Instagram arka plan işi hatası ({news_id}): {exc}")
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message="Instagram taslağı hazırlanırken beklenmeyen bir hata oluştu.",
        )
    else:
        _update_job(
            job_id,
            status="completed",
            progress=100,
            message=draft["message"],
            result=draft,
        )


def start_instagram_draft_job(news_id: int) -> dict:
    """Bir haber için tek bir üretim işi başlatır veya mevcut işi döndürür."""
    with _lock:
        _remove_expired_jobs()
        existing = next(
            (
                job
                for job in _jobs.values()
                if job["news_id"] == news_id
                and job["status"] in {"queued", "running"}
            ),
            None,
        )
        if existing is not None:
            return _public_job(existing)

        job_id = uuid4().hex
        job = {
            "id": job_id,
            "news_id": news_id,
            "status": "queued",
            "progress": 5,
            "message": "İşlem kuyruğa alındı.",
            "result": None,
            "updated_at": _now(),
        }
        _jobs[job_id] = job

    _executor.submit(_run_job, job_id, news_id)
    return _public_job(job)


def get_instagram_draft_job(job_id: str) -> dict | None:
    """İşin anlık durumunu döndürür."""
    with _lock:
        _remove_expired_jobs()
        job = _jobs.get(job_id)
        return _public_job(job) if job is not None else None
