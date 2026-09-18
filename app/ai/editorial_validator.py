"""OtoTrendTR Instagram taslakları için yayın öncesi kural denetimleri."""

from __future__ import annotations

import re
from collections.abc import Iterable


NUMBER_RE = re.compile(
    r"(?<![\w#])\d+(?:[.,]\d+)?",
    re.UNICODE,
)
QUOTE_RE = re.compile(r'["“]([^"”]*)["”]')

REQUIRED_CAPTION_MARKERS = (
    "📊 ÖNE ÇIKAN DİKKAT ÇEKİCİ DETAYLAR:",
    "💡 EDİTÖR NOTU:",
    "Yorumlarda buluşalım! 👇",
    "⚠️ Bilgilendirme: Reklam değildir.",
    "📍 KAYNAKLAR:",
    "#OtoTrendTR",
)


def _as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _numbers(text: str) -> set[str]:
    """Sayıların ondalık ayıracını normalize ederek karşılaştırır."""
    return {
        match.group().replace(",", ".")
        for match in NUMBER_RE.finditer(text)
    }


def _editorial_caption_body(caption: str) -> str:
    """Kaynak/telif satırları dışındaki iddia bölümünü ayırır."""
    return re.split(
        r"(?:^|\n)⚠️\s*Bilgilendirme:|(?:^|\n)📍\s*KAYNAKLAR:",
        caption,
        maxsplit=1,
    )[0]


def validate_instagram_draft(
    draft: dict[str, object],
    *,
    source_name: str,
    source_date: str,
    source_text: str,
) -> list[str]:
    """Taslağın rehberdeki biçim ve doğrulanabilirlik kurallarını denetler.

    Dönen liste boşsa taslak yayın öncesi kontrollerden geçmiştir. Bu denetim
    kaynak doğrulamasının yerini almaz; yalnızca taslak içi tutarlılığı korur.
    """
    errors: list[str] = []
    caption = _as_text(draft.get("instagram_caption"))
    hashtags = _as_text(draft.get("hashtags"))
    title = _as_text(draft.get("instagram_title"))
    photo_direction = _as_text(draft.get("photo_direction"))

    if not title:
        errors.append("Görsel ana başlığı boş.")
    elif len(title) > 100:
        errors.append("Görsel ana başlığı 100 karakteri aşıyor.")

    if not photo_direction:
        errors.append("Otomatik görsel için uygulama notu eksik.")
    elif len(photo_direction) > 220:
        errors.append("Otomatik görsel uygulama notu 220 karakteri aşıyor.")

    if not caption:
        errors.append("Instagram açıklaması boş.")
        return errors

    for marker in REQUIRED_CAPTION_MARKERS:
        if marker not in caption:
            errors.append(f"Caption zorunlu bölümü içermiyor: {marker}")

    detail_count = len(
        re.findall(r"(?:^|\n)🔹\s*", caption)
    )
    if detail_count != 4:
        errors.append("Caption'da tam olarak 4 öne çıkan detay bulunmalı.")

    if "#OtoTrendTR" not in hashtags:
        errors.append("Hashtag alanında #OtoTrendTR bulunmalı.")

    expected_source = f"📍 KAYNAKLAR: {source_name} ({source_date})"
    if expected_source not in caption:
        errors.append("Caption kaynak ve tarih satırını eksiksiz içermiyor.")

    for quote in QUOTE_RE.findall(caption):
        if len(quote.split()) > 15:
            errors.append("Doğrudan alıntı 15 kelimeyi geçemez.")
            break

    caption_numbers = _numbers(_editorial_caption_body(caption))
    source_numbers = _numbers(source_text)
    missing_numbers = caption_numbers - source_numbers
    if missing_numbers:
        values = ", ".join(sorted(missing_numbers))
        errors.append(
            "Caption'daki sayısal iddialar haber metninde de yer almalı: "
            f"{values}."
        )

    return errors


def format_validation_notes(notes: object) -> list[str]:
    """AI'ın editöre ilettiği inceleme notlarını güvenli bir listeye dönüştürür."""
    if isinstance(notes, str):
        return [notes.strip()] if notes.strip() else []
    if isinstance(notes, Iterable):
        return [str(note).strip() for note in notes if str(note).strip()]
    return []
