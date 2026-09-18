import json
import time
from datetime import datetime

from app.ai.cleaner import clean_text, prompt_size_kb
from app.ai.provider import instagram_chat
from app.ai.parser import parse_json
from app.ai.editorial_validator import (
    format_validation_notes,
    validate_instagram_draft,
)
from app.ai.turkish_quality import (
    normalize_instagram_draft,
    validate_turkish_instagram_draft,
)
from app.config import AI_TURKISH_QUALITY_RETRIES


PROMPT_TEMPLATE = """
OtoTrendTR için Türkçe, nesnel ve özgün bir Instagram haber taslağı üret.
SADECE geçerli JSON döndür; Markdown, açıklama ve yer tutucu kullanma.

HABER dışındaki hiçbir teknik veri, fiyat, tarih, kişi, mevzuat veya yorum ekleme.
Sayısal iddia yalnızca HABER'de geçiyorsa kullanılabilir. Doğrudan alıntı 15
kelimeyi geçmesin. Mevzuat/vergi HABER'de yoksa hiç anma.

GÖRSEL: AI ile fotoğraf üretme. Kaynak fotoğraf kullanılacak. instagram_title
tek ana başlıktır; güçlü, anlamı korunmuş, en çok 100 karakter olsun.
photo_direction en çok 140 karakterle gerçek fotoğrafta korunacak kadrajı anlat.
Tasarım 1080×1512, fotoğraf ağırlıklı, orijinal OtoTrendTR logosu ve altta
"HABERİN DETAYLARI AÇIKLAMADA" ifadesini kullanır; başka görsel metin/kart yok.

METİN ALANLARI:
- intro en fazla iki kısa cümle olsun.
- details alanı, HABER'deki farklı ayrıntıları özgün biçimde anlatan TAM DÖRT
  kısa cümlelik JSON listesi olsun.
- editor_note kişisel görüş içermeyen tek kısa cümle; question tek açık uçlu
  soru olsun.
- hashtags en fazla 8 adet ve mutlaka #OtoTrendTR içersin.
- Reklam, övgü, vaat, duygusal anlatım veya tahmin kullanma. "heyecan verici",
  "efsanevi", "hayaller", "büyüleyecek", "hazır mısınız" gibi ifadeleri
  yazma. Her cümle yalnızca HABER'de doğrulanabilen nesnel bilgi içersin.
- Tüm metin alanları doğal ve akıcı Türkçe olmalı; bozuk karakter, İngilizce
  kalıntı veya yabancı harf kullanma. Marka, model ve resmî etkinlik adı hariç
  yabancı kelime kullanma.
- Türkiye elektrikli araç/mevzuat iddiası varsa validation_notes'a
  "Mevzuat ve vergi oranı editör tarafından resmi kaynaktan doğrulanmalı." ekle.

SADECE aşağıdaki JSON nesnesini döndür.

{{
  "instagram_title": "",
  "photo_direction": "",
  "intro": "",
  "details": ["", "", "", ""],
  "editor_note": "",
  "question": "",
  "hashtags": "",
  "validation_notes": []
}}

KAYNAK: {source_name}
KAYNAK TARİHİ: {source_date}
GÖRSEL DURUMU: {visual_context}
HABER BAŞLIĞI: {headline}
HABER:
{news}
"""


TURKISH_MONTHS = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)


def _source_date(value: datetime | None) -> str:
    date = value or datetime.now()
    return f"{TURKISH_MONTHS[date.month - 1]} {date.year}"


def _short_text(value: object) -> str:
    """Model alanlarını tek satırlık, arayüzde güvenli metne dönüştürür."""
    return " ".join(str(value or "").strip().split())


def _details(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Instagram AI çıktısındaki details alanı liste olmalı.")

    items = [_short_text(item) for item in value]
    if len(items) != 4 or any(not item for item in items):
        raise ValueError(
            "Instagram AI çıktısında tam dört kısa öne çıkan detay olmalı."
        )
    return items


def _compose_caption(
    *,
    title: str,
    intro: str,
    details: list[str],
    editor_note: str,
    question: str,
    source_name: str,
    source_date: str,
    hashtags: str,
) -> str:
    """Sabit yayın unsurlarını modelden bağımsız olarak uygular."""
    normalized_question = _short_text(question).rstrip(".!")
    if normalized_question and not normalized_question.endswith("?"):
        normalized_question += "?"

    return "\n".join(
        (
            f"🇹🇷 🚗 {_short_text(title).upper()}",
            "",
            _short_text(intro),
            "",
            "📊 ÖNE ÇIKAN DİKKAT ÇEKİCİ DETAYLAR:",
            *(f"🔹 {item}" for item in details),
            "",
            "💡 EDİTÖR NOTU:",
            _short_text(editor_note),
            "",
            f"💬 {normalized_question} Yorumlarda buluşalım! 👇",
            "",
            (
                "⚠️ Bilgilendirme: Reklam değildir. "
                f"{source_name} verileri baz alınarak hazırlanmıştır."
            ),
            f"📍 KAYNAKLAR: {source_name} ({source_date})",
            hashtags,
        )
    )


def _normalize_hashtags(value: object) -> str:
    tags = [tag for tag in _short_text(value).split() if tag.startswith("#")]
    if "#OtoTrendTR" not in tags:
        tags.append("#OtoTrendTR")
    return " ".join(tags[:8])


def _normalize_model_draft(result: dict[str, object]) -> dict[str, object]:
    """Zorunlu alanları kontrol eder ve model metnini kayda hazırlamadan temizler."""
    required_fields = (
        "instagram_title",
        "photo_direction",
        "intro",
        "details",
        "editor_note",
        "question",
        "hashtags",
    )
    for field in required_fields:
        if field not in result:
            raise ValueError(f"Instagram AI çıktısında eksik alan: {field}")

    normalized = normalize_instagram_draft(result)
    normalized["details"] = _details(normalized["details"])
    normalized["hashtags"] = _normalize_hashtags(normalized["hashtags"])
    return normalized


def _quality_retry_prompt(
    prompt: str,
    errors: list[str],
    draft: dict[str, object],
) -> str:
    previous_draft = json.dumps(
        {
            "instagram_title": draft.get("instagram_title", ""),
            "intro": draft.get("intro", ""),
            "details": draft.get("details", []),
            "editor_note": draft.get("editor_note", ""),
        },
        ensure_ascii=False,
    )
    return (
        prompt
        + "\nÖnceki taslak:\n"
        + previous_draft
        + "\nBu taslak kabul edilmedi: "
        + "; ".join(errors)
        + ". Yalnızca doğrulanabilir, akıcı ve nesnel Türkçe ile yeniden yaz."
    )


def _visual_brief(
    headline: str,
    photo_direction: str,
    visual_context: str,
) -> str:
    """Otomatik seçilen görselle uygulanacak sabit tasarım notu."""
    return "\n".join(
        (
            "OTO TRENDTR GÖRSEL UYGULAMA NOTU",
            "Tuval: 1080 × 1512 px, 9:14 dikey Instagram formatı.",
            "Fotoğraf: Sistem tarafından otomatik seçilen kaynak görselini kullan; "
            "AI ile üretilmiş ek fotoğraf kullanma.",
            f"Görsel kaynak durumu: {visual_context}",
            "Fotoğraf ağırlığı: Yaklaşık %70-80; araç/olay gerçekliğini, modelini, "
            "rengini ve ayrıntılarını değiştirme.",
            f"Fotoğraf seçimi/kadrajı: {photo_direction}",
            f"Tek ana başlık: {headline}",
            "Başlık: Büyük, yüksek kontrastlı ve telefonda okunabilir olsun; "
            "gerekirse tek başlık olarak 2-4 satıra böl.",
            "Logo: Yalnızca orijinal, şeffaf arka planlı "
            "/static/images/ototrendtr-logo-cutout.png dosyasını "
            "kullan; varsayılan sol üst, gerekirse fotoğrafı kapatmayan boş alan.",
            "Alt sabit ifade: HABERİN DETAYLARI AÇIKLAMADA.",
            "Grafik: Kullanıcı özellikle istemedikçe kart, rozet, ok, ikon, emoji görseli, "
            "sahte logo veya dekoratif efekt kullanma.",
        )
    )


def process_instagram(
    news: str,
    *,
    source_name: str = "Resmi kaynak",
    published_at: datetime | None = None,
    headline: str = "",
    visual_context: str = "Görsel kaynağı henüz belirlenmedi.",
):

    metrics = {
        "prompt_time": 0.0,
        "ollama_time": 0.0,
        "parse_time": 0.0,
        "prompt_kb": 0.0,
        "response_kb": 0.0,
    }

    # ==========================================================
    # PROMPT
    # ==========================================================

    start = time.perf_counter()

    news = clean_text(news)

    if not news:
        raise ValueError(
            "Instagram AI için haber içeriği bulunamadı."
        )

    prompt = PROMPT_TEMPLATE.format(
        news=news,
        source_name=source_name.strip() or "Resmi kaynak",
        source_date=_source_date(published_at),
        headline=headline.strip(),
        visual_context=visual_context.strip() or "Görsel kaynağı henüz belirlenmedi.",
    )

    metrics["prompt_time"] = (
        time.perf_counter() - start
    )

    metrics["prompt_kb"] = prompt_size_kb(
        prompt
    )

    # ==========================================================
    # AI + TÜRKÇE KALİTE DENETİMİ
    # ==========================================================

    start = time.perf_counter()
    result = None
    candidate: dict[str, object] = {}
    quality_errors: list[str] = []

    for attempt in range(AI_TURKISH_QUALITY_RETRIES + 1):
        request_prompt = prompt if attempt == 0 else _quality_retry_prompt(
            prompt,
            quality_errors,
            candidate,
        )
        response = instagram_chat(request_prompt)
        metrics["response_kb"] = round(
            len(response.encode("utf-8")) / 1024,
            2,
        )

        # Emoji içeren yanıtı bazı Windows konsollarına ham biçimde yazmak
        # UnicodeEncodeError oluşturabilir. İçeriği değil yalnızca boyutu günlüğe al.
        print("Instagram AI yanıtı alındı " f"({len(response)} karakter).")

        parse_start = time.perf_counter()
        try:
            candidate = _normalize_model_draft(parse_json(response))
        except ValueError as exc:
            metrics["parse_time"] += time.perf_counter() - parse_start
            quality_errors = [str(exc)]
            continue
        metrics["parse_time"] += time.perf_counter() - parse_start

        quality_errors = validate_turkish_instagram_draft(candidate)
        if not quality_errors:
            result = candidate
            break

    metrics["ollama_time"] = time.perf_counter() - start
    metrics["quality_attempts"] = attempt + 1

    if result is None:
        raise ValueError(
            "Instagram Türkçe kalite kontrolünden geçemedi: "
            + "; ".join(quality_errors)
        )

    source_name = source_name.strip() or "Resmi kaynak"
    source_date = _source_date(published_at)
    result["instagram_caption"] = _compose_caption(
        title=result["instagram_title"],
        intro=result["intro"],
        details=result["details"],
        editor_note=result["editor_note"],
        question=result["question"],
        source_name=source_name,
        source_date=source_date,
        hashtags=result["hashtags"],
    )

    result["validation_notes"] = format_validation_notes(
        result.get("validation_notes")
    )

    result["visual_brief"] = _visual_brief(
        result["instagram_title"],
        result["photo_direction"],
        visual_context,
    )
    # Mevcut veri modeliyle uyumluluk için uygulama notu bu alanda saklanır.
    result["image_prompt"] = result["visual_brief"]

    errors = validate_instagram_draft(
        result,
        source_name=source_name,
        source_date=source_date,
        source_text=f"{headline}\n{news}",
    )
    if errors:
        raise ValueError("Yayın rehberi denetimi başarısız: " + " ".join(errors))

    return result, metrics
