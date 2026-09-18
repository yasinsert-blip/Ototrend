from app.services.dashboard_service import (
    get_dashboard_stats,
)

from app.database.database import SessionLocal

from typing import List
from typing import Literal
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Request,
    Form,
    HTTPException,
    Query,
)

from fastapi.responses import (
    RedirectResponse,
    JSONResponse,
)

from fastapi.templating import Jinja2Templates

from app.ai.worker import process_ai_news
from app.ai.instagram_pipeline import process_instagram

from app.database.crud import (
    get_news,
    get_news_by_id,
    update_news_editor,
    update_instagram_content,
    bulk_update_status,
    bulk_delete_news,
)

from app.services.editor_service import (
    get_brand_list,
    get_category_list,
)
from app.services.visual_source_service import (
    get_selected_visual,
    resolve_and_save_visual,
    visual_for_response,
)
from app.services.instagram_visual_service import (
    VisualRenderError,
    render_instagram_visual,
    rendered_visual_url,
)
from app.services.instagram_draft_service import create_instagram_draft
from app.services.news_selection import plain_text
from app.services.similar_news import suggest_similar, group_confirmed, ungroup
from app.security import require_authenticated
from app.services.instagram_job_service import (
    get_instagram_draft_job,
    start_instagram_draft_job,
)


router = APIRouter()
MAX_BULK_INSTAGRAM_DRAFTS = 3


templates = Jinja2Templates(
    directory="app/templates"
)


# ==========================================================
# NEWS DETAIL
# ==========================================================

@router.get("/news/{news_id}")
def news_detail(
    request: Request,
    news_id: int,
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    news = get_news_by_id(news_id)

    if news is None:
        raise HTTPException(
            status_code=404,
            detail="News not found",
        )

    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={
            "request": request,
            "news": news,
        },
    )


# ==========================================================
# AI EDITOR PANEL
# ==========================================================

@router.get("/editor")
def editor_panel(
    request: Request,
    keyword: str = "",
    status: str = "",
    brand: str = "",
    category: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_importance: int = Query(0, ge=0, le=10),
    sort: Literal["newest", "oldest", "importance", "news_value"] = "newest",
    section: Literal["all", "important", "review", "ready"] = "all",
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    result = get_news(
        keyword=keyword.strip(), status=status or None, brand=brand or None,
        category=category or None, page=page, page_size=page_size,
        min_importance=min_importance, sort=sort, section=section,
    )
    filters = {
        "keyword": keyword.strip(), "status": status, "brand": brand,
        "category": category, "min_importance": min_importance,
        "sort": sort, "page_size": page_size, "section": section,
    }
    page_number = result["page"]
    pagination = {
        "page": page_number, "total_pages": result["total_pages"],
        "total": result["total"],
        "first": (page_number - 1) * page_size + 1 if result["total"] else 0,
        "last": min(page_number * page_size, result["total"]),
        "links": [
            {"number": number, "url": "/editor?" + urlencode({**filters, "page": number})}
            for number in range(max(1, page_number - 2), min(result["total_pages"], page_number + 2) + 1)
        ],
        "previous": "/editor?" + urlencode({**filters, "page": page_number - 1}) if page_number > 1 else None,
        "next": "/editor?" + urlencode({**filters, "page": page_number + 1}) if page_number < result["total_pages"] else None,
    }

    brands = get_brand_list()

    categories = get_category_list()

    db = SessionLocal()

    try:

        stats = get_dashboard_stats(db)

    finally:

        db.close()

    return templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={
            "request": request,
            "news_list": result["items"],
            "pagination": pagination,
            "brands": brands,
            "categories": categories,
            "stats": stats,
        },
    )

# ==========================================================
# BULK ACTION
# ==========================================================

@router.post("/editor/bulk")
def bulk_action(
    request: Request,
    action: str = Form(...),
    news_ids: List[int] = Form(...),
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    # Tarayıcıdaki toplu işlem ekranı JSON yanıtı bekler. Normal form
    # gönderimleri ise işlem sonunda editör listesine geri yönlendirilir.
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    message = f"{len(news_ids)} haber başarıyla işlendi."
    extra_response = {}

    # ------------------------------------------------------
    # AI İşle
    # ------------------------------------------------------

    if action == "ai":

        skipped_ids = []
        for news_id in news_ids:
            try:
                process_ai_news(news_id)
            except ValueError:
                skipped_ids.append(news_id)
        if skipped_ids:
            message = "Yeterli kaynak metni olmadığı için AI işlemi atlandı: " + ", ".join(
                f"#{news_id}" for news_id in skipped_ids
            )
            extra_response["skipped_ids"] = skipped_ids

    # ------------------------------------------------------
    # Instagram taslağı
    # ------------------------------------------------------

    elif action == "instagram_generate":

        if len(news_ids) > MAX_BULK_INSTAGRAM_DRAFTS:
            detail = (
                "Toplu Instagram üretiminde aynı anda en fazla "
                f"{MAX_BULK_INSTAGRAM_DRAFTS} haber seçebilirsiniz."
            )
            if is_ajax:
                return JSONResponse(
                    {"success": False, "message": detail},
                    status_code=422,
                )
            return RedirectResponse(url="/editor", status_code=303)

        completed_ids = []
        failed_ids = []
        for news_id in news_ids:
            try:
                create_instagram_draft(news_id)
                completed_ids.append(news_id)
            except Exception as exc:
                print(f"❌ Toplu Instagram taslağı hatası ({news_id}): {exc}")
                failed_ids.append(news_id)

        message = f"{len(completed_ids)} Instagram taslağı oluşturuldu."
        if failed_ids:
            message += " Oluşturulamayan haberler: " + ", ".join(
                f"#{news_id}" for news_id in failed_ids
            )
        extra_response = {
            "completed_ids": completed_ids,
            "failed_ids": failed_ids,
        }
        if not completed_ids and is_ajax:
            return JSONResponse(
                {"success": False, "message": message, **extra_response},
                status_code=422,
            )

    # ------------------------------------------------------
    # Editör İnceleme
    # ------------------------------------------------------

    elif action == "editor_review":

        bulk_update_status(
            news_ids,
            "editor_review",
        )

    # ------------------------------------------------------
    # Instagram Hazır
    # ------------------------------------------------------

    elif action == "instagram_ready":

        bulk_update_status(
            news_ids,
            "instagram_ready",
        )

    # ------------------------------------------------------
    # Planla
    # ------------------------------------------------------

    elif action == "scheduled":

        bulk_update_status(
            news_ids,
            "scheduled",
        )

    # ------------------------------------------------------
    # Yayınla
    # ------------------------------------------------------

    elif action == "published":

        bulk_update_status(
            news_ids,
            "published",
        )

    # ------------------------------------------------------
    # Arşivle
    # ------------------------------------------------------

    elif action == "archived":

        bulk_update_status(
            news_ids,
            "archived",
        )

    # ------------------------------------------------------
    # Sil
    # ------------------------------------------------------

    elif action == "delete":

        bulk_delete_news(
            news_ids,
        )

    # ------------------------------------------------------
    # AJAX kontrolü
    # ------------------------------------------------------

    # ------------------------------------------------------
    # AJAX JSON cevap
    # ------------------------------------------------------

    if is_ajax:

        return JSONResponse(
            {
                "success": True,
                "action": action,
                "count": len(news_ids),
                "message": message,
                **extra_response,
            }
        )

    # ------------------------------------------------------
    # Normal form gönderimi
    # ------------------------------------------------------

    return RedirectResponse(
        url="/editor",
        status_code=303,
    )
# ==========================================================
# AI EDITOR DETAIL
# ==========================================================

@router.get("/editor/{news_id}")
def editor_detail(
    request: Request,
    news_id: int,
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    news = get_news_by_id(news_id)

    if news is None:
        raise HTTPException(
            status_code=404,
            detail="News not found",
        )

    return templates.TemplateResponse(
        request=request,
        name="editor_detail.html",
        context={
            "request": request,
            "news": news,
            "source_text": plain_text(news.content),
            "similar_news": _similar_suggestions(news),
        },
    )


def _similar_suggestions(news):
    with SessionLocal() as db:
        return suggest_similar(db, news)


@router.post("/editor/{news_id}/group")
def confirm_news_group(request: Request, news_id: int, parent_id: int = Form(...), confirmed: bool = Form(False)):
    require_authenticated(request)
    if not confirmed:
        raise HTTPException(422, "Haberleri karşılaştırıp onay kutusunu işaretleyin.")
    with SessionLocal() as db:
        try:
            group_confirmed(db, news_id, parent_id)
        except ValueError as error:
            db.rollback()
            raise HTTPException(409, str(error))
    return RedirectResponse(f"/editor/{news_id}", status_code=303)


@router.post("/editor/{news_id}/ungroup")
def separate_news_group(request: Request, news_id: int):
    require_authenticated(request)
    with SessionLocal() as db:
        try:
            ungroup(db, news_id)
        except ValueError as error:
            db.rollback()
            raise HTTPException(409, str(error))
    return RedirectResponse(f"/editor/{news_id}", status_code=303)


# ==========================================================
# EDITOR DETAIL SAVE
# ==========================================================

@router.post("/editor/{news_id}")
def save_editor(
    request: Request,
    news_id: int,

    translated_title: str = Form(...),
    summary: str = Form(...),
    category: str = Form(...),
    brand: str = Form(...),
    importance: int = Form(...),
    editor_note: str = Form(""),
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    update_news_editor(
        news_id=news_id,
        translated_title=translated_title,
        summary=summary,
        category=category,
        brand=brand,
        importance=importance,
        editor_note=editor_note,
    )

    return RedirectResponse(
        url=f"/editor/{news_id}",
        status_code=303,
    )


# ==========================================================
# AI EDITOR INLINE AJAX SAVE
# ==========================================================

@router.post("/editor/{news_id}/save")
def save_editor_inline(
    request: Request,
    news_id: int,

    translated_title: str = Form(""),
    summary: str = Form(""),

    brand: str = Form(""),
    category: str = Form(""),

    importance: int = Form(...),

    instagram_title: str = Form(""),
    instagram_caption: str = Form(""),
    hashtags: str = Form(""),
    image_prompt: str = Form(""),
):

    # ------------------------------------------------------
    # AUTH
    # ------------------------------------------------------

    if not request.session.get("authenticated"):
        return JSONResponse(
            {
                "success": False,
                "message": "Oturum geçersiz.",
            },
            status_code=401,
        )

    # ------------------------------------------------------
    # HABER KONTROLÜ
    # ------------------------------------------------------

    news = get_news_by_id(news_id)

    if news is None:
        return JSONResponse(
            {
                "success": False,
                "message": "Haber bulunamadı.",
            },
            status_code=404,
        )

    # ------------------------------------------------------
    # ÖNEM KONTROLÜ
    # ------------------------------------------------------

    if importance < 1 or importance > 10:

        return JSONResponse(
            {
                "success": False,
                "message": "Önem değeri 1 ile 10 arasında olmalıdır.",
            },
            status_code=400,
        )

    try:

        # --------------------------------------------------
        # AI / EDITOR ALANLARI
        # --------------------------------------------------

        update_news_editor(
            news_id=news_id,
            translated_title=translated_title,
            summary=summary,
            category=category,
            brand=brand,
            importance=importance,
            editor_note="",
        )

        # --------------------------------------------------
        # INSTAGRAM ALANLARI
        # --------------------------------------------------

        update_instagram_content(
            news_id=news_id,
            instagram_title=instagram_title,
            instagram_caption=instagram_caption,
            hashtags=hashtags,
            image_prompt=image_prompt,
            # Satır içi editör hem haber hem Instagram alanlarını aynı anda
            # gönderir. Yalnızca haber düzenlemek, kaydı Instagram taslağına
            # taşımamalıdır.
            mark_as_draft=False,
        )

        # --------------------------------------------------
        # BAŞARILI
        # --------------------------------------------------

        return JSONResponse(
            {
                "success": True,
                "news_id": news_id,
                "message": (
                    f"Haber #{news_id} başarıyla kaydedildi."
                ),
            }
        )

    except Exception as e:

        print(
            f"❌ Editör kayıt hatası ({news_id}): {e}"
        )

        return JSONResponse(
            {
                "success": False,
                "message": (
                    "Haber kaydedilirken bir hata oluştu."
                ),
            },
            status_code=500,
        )


# ==========================================================
# INSTAGRAM EDITOR
# ==========================================================

@router.get("/instagram/{news_id}")
def instagram_editor(
    request: Request,
    news_id: int,
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    news = get_news_by_id(news_id)

    if news is None:
        raise HTTPException(
            status_code=404,
            detail="News not found",
        )

    return templates.TemplateResponse(
        request=request,
        name="instagram_editor.html",
        context={
            "request": request,
            "news": news,
            "visual_image": visual_for_response(
                get_selected_visual(news_id)
            ),
            "rendered_image": rendered_visual_url(news_id),
        },
    )


# ==========================================================
# INSTAGRAM SAVE
# ==========================================================

@router.post("/instagram/{news_id}")
def save_instagram_editor(
    request: Request,
    news_id: int,

    instagram_title: str = Form(...),
    instagram_caption: str = Form(...),
    hashtags: str = Form(...),
    image_prompt: str = Form(...),
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    update_instagram_content(
        news_id=news_id,
        instagram_title=instagram_title,
        instagram_caption=instagram_caption,
        hashtags=hashtags,
        image_prompt=image_prompt,
    )

    return RedirectResponse(
        url=f"/instagram/{news_id}",
        status_code=303,
    )

# ==========================================================
# INSTAGRAM GÖRSEL KAYNAĞI
# ==========================================================

@router.post("/instagram/{news_id}/resolve-image")
def resolve_instagram_image(
    request: Request,
    news_id: int,
):
    """Haber için otomatik görsel adayı bulur ve kaynak kaydını saklar."""
    if not request.session.get("authenticated"):
        return JSONResponse(
            {"success": False, "message": "Oturum geçersiz."},
            status_code=401,
        )

    news = get_news_by_id(news_id)
    if news is None:
        return JSONResponse(
            {"success": False, "message": "Haber bulunamadı."},
            status_code=404,
        )

    try:
        image = resolve_and_save_visual(news)
        return JSONResponse(
            {
                "success": True,
                "news_id": news_id,
                "visual_image": visual_for_response(image),
            }
        )
    except Exception as e:
        print(f"❌ Görsel kaynak çözümleme hatası ({news_id}): {e}")
        return JSONResponse(
            {
                "success": False,
                "message": "Görsel kaynağı bulunurken bir hata oluştu.",
            },
            status_code=500,
        )


# ==========================================================
# INSTAGRAM GÖRSEL OLUŞTUR
# ==========================================================

@router.post("/instagram/{news_id}/render")
def render_instagram_image(
    request: Request,
    news_id: int,
    instagram_title: str = Form(""),
):
    """Otomatik seçilen kaynak fotoğrafından nihai Instagram görselini üretir."""
    if not request.session.get("authenticated"):
        return JSONResponse(
            {"success": False, "message": "Oturum geçersiz."},
            status_code=401,
        )

    news = get_news_by_id(news_id)
    if news is None:
        return JSONResponse(
            {"success": False, "message": "Haber bulunamadı."},
            status_code=404,
        )

    headline = instagram_title.strip() or (news.instagram_title or "").strip()
    if not headline:
        return JSONResponse(
            {
                "success": False,
                "message": "Önce Instagram başlığını oluşturun.",
            },
            status_code=400,
        )

    try:
        image = resolve_and_save_visual(news)
        if image is None:
            raise VisualRenderError(
                "Kaynak veya açık lisanslı uygun görsel bulunamadı."
            )
        rendered = render_instagram_visual(
            news_id=news_id,
            headline=headline,
            image_url=image.image_url,
        )
        return JSONResponse(
            {
                "success": True,
                "news_id": news_id,
                "message": "Instagram görseli oluşturuldu.",
                "generated_image": rendered.public_url,
                "visual_image": visual_for_response(image),
            }
        )
    except VisualRenderError as exc:
        return JSONResponse(
            {"success": False, "message": str(exc)},
            status_code=422,
        )
    except Exception as exc:
        print(f"❌ Instagram görsel üretim hatası ({news_id}): {exc}")
        return JSONResponse(
            {
                "success": False,
                "message": "Instagram görseli oluşturulurken bir hata oluştu.",
            },
            status_code=500,
        )


# ==========================================================
# INSTAGRAM AI GENERATE
# ==========================================================

@router.post("/instagram/{news_id}/generate")
def generate_instagram_ai(
    request: Request,
    news_id: int,
):

    # ------------------------------------------------------
    # AUTH
    # ------------------------------------------------------

    if not request.session.get("authenticated"):
        return JSONResponse(
            {
                "success": False,
                "message": "Oturum geçersiz.",
            },
            status_code=401,
        )

    try:
        draft = create_instagram_draft(news_id)
        return JSONResponse({"success": True, **draft})
    except (LookupError, ValueError) as exc:
        return JSONResponse(
            {
                "success": False,
                "message": str(exc),
            },
            status_code=404 if isinstance(exc, LookupError) else 422,
        )
    except Exception as exc:
        print(f"Instagram AI hatası ({news_id}): {exc}")
        return JSONResponse(
            {
                "success": False,
                "message": "Instagram içeriği oluşturulurken bir hata oluştu.",
            },
            status_code=500,
        )


@router.post("/instagram/{news_id}/generate/start")
def start_instagram_ai_job(request: Request, news_id: int):
    """Tarayıcıyı bekletmeden üretim işini kuyruğa alır."""
    if not request.session.get("authenticated"):
        return JSONResponse(
            {"success": False, "message": "Oturum geçersiz."},
            status_code=401,
        )

    if get_news_by_id(news_id) is None:
        return JSONResponse(
            {"success": False, "message": "Haber bulunamadı."},
            status_code=404,
        )

    job = start_instagram_draft_job(news_id)
    return JSONResponse(
        {
            "success": True,
            "message": job["message"],
            "job": job,
        },
        status_code=202,
    )


@router.get("/instagram/jobs/{job_id}")
def instagram_ai_job_status(request: Request, job_id: str):
    """Instagram üretim işinin arayüzde gösterilecek ilerlemesini döndürür."""
    if not request.session.get("authenticated"):
        return JSONResponse(
            {"success": False, "message": "Oturum geçersiz."},
            status_code=401,
        )

    job = get_instagram_draft_job(job_id)
    if job is None:
        return JSONResponse(
            {
                "success": False,
                "message": "İş bulunamadı veya sunucu yeniden başlatıldı.",
            },
            status_code=404,
        )

    return JSONResponse({"success": True, "job": job})
# ==========================================================
# SINGLE AI REPROCESS
# ==========================================================

@router.post("/editor/{news_id}/ai")
def rerun_ai(
    request: Request,
    news_id: int,
):

    if not request.session.get("authenticated"):
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    news = get_news_by_id(news_id)

    if news is None:
        raise HTTPException(
            status_code=404,
            detail="News not found",
        )

    try:
        process_ai_news(news_id)
    except ValueError as error:
        return JSONResponse({"success": False, "message": str(error)}, status_code=422)

    return JSONResponse(
        {
            "success": True,
            "message": "İşlem başarıyla tamamlandı.",
        }
    )
