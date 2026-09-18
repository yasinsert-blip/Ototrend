"""Tekli ve toplu Instagram taslağı üretiminde kullanılan ortak iş akışı."""

from __future__ import annotations

from collections.abc import Callable

from app.ai.instagram_pipeline import process_instagram
from app.database.crud import get_news_by_id, update_instagram_content
from app.services.news_selection import content_skip_reason, plain_text
from app.services.fact_check import check_facts
from app.services.instagram_visual_service import VisualRenderError, render_instagram_visual
from app.services.visual_source_service import (
    resolve_and_save_visual,
    visual_for_response,
)


class InstagramDraftError(ValueError):
    """Editöre güvenli biçimde gösterilebilecek taslak üretim hatası."""


ProgressReporter = Callable[[int, str], None]


def create_instagram_draft(
    news_id: int,
    *,
    report_progress: ProgressReporter | None = None,
) -> dict:
    """Haber için metin, açıklama ve kaynak fotoğraflı Instagram taslağı üretir."""
    def report(percent: int, message: str) -> None:
        if report_progress is not None:
            report_progress(percent, message)

    report(10, "Haber içeriği kontrol ediliyor.")
    news = get_news_by_id(news_id)
    if news is None:
        raise LookupError("Haber bulunamadı.")

    reason = content_skip_reason(news)
    if reason:
        raise InstagramDraftError(reason)
    news_text = plain_text(news.content)

    report(22, "Kaynak görseli kontrol ediliyor.")
    image = resolve_and_save_visual(news)
    visual_image = visual_for_response(image)

    report(38, "Türkçe başlık ve açıklama hazırlanıyor.")
    result, metrics = process_instagram(
        news_text,
        source_name=news.source or "Resmi kaynak",
        published_at=news.published_at or news.created_at,
        headline=news.translated_title or news.title or "",
        visual_context=visual_image["message"] or "",
    )

    report(72, "Metin kalite kontrolünden geçiriliyor ve taslak kaydediliyor.")
    fact_issues = check_facts((news.title or "") + "\n" + news_text, result)
    update_instagram_content(
        news_id=news_id,
        instagram_title=result["instagram_title"],
        instagram_caption=result["instagram_caption"],
        hashtags=result["hashtags"],
        image_prompt=result["image_prompt"],
        fact_check_notes="\n".join(fact_issues),
    )

    generated_image = None
    visual_render_error = None
    if image is not None:
        try:
            report(84, "Instagram görseli hazırlanıyor.")
            generated_image = render_instagram_visual(
                news_id=news_id,
                headline=result["instagram_title"],
                image_url=image.image_url,
            ).public_url
        except VisualRenderError as exc:
            # Metin taslağı kaydedildi; görsel gerektiğinde editörden yeniden üretilebilir.
            visual_render_error = str(exc)

    report(100, "Taslak kaynak doğrulaması bekliyor." if fact_issues else "Instagram taslağı hazır.")

    return {
        "news_id": news_id,
        "message": (f"Haber #{news_id} için taslak oluşturuldu; kaynak doğrulaması gerekiyor."
                    if fact_issues else f"Haber #{news_id} için Instagram taslağı oluşturuldu."),
        "data": {
            "instagram_title": result.get("instagram_title", ""),
            "instagram_caption": result.get("instagram_caption", ""),
            "hashtags": result.get("hashtags", ""),
            "image_prompt": result.get("image_prompt", ""),
            "photo_direction": result.get("photo_direction", ""),
            "visual_brief": result.get("visual_brief", ""),
            "validation_notes": result.get("validation_notes", []),
            "fact_check_notes": fact_issues,
            "visual_image": visual_image,
            "generated_image": generated_image,
            "visual_render_error": visual_render_error,
        },
        "metrics": metrics,
    }
