"""OtoTrendTR haber çıktılarında Türkçe okunabilirliği koruyan denetimler."""

from __future__ import annotations

import re
import unicodedata

from app.ai.cleaner import repair_mojibake


MOJIBAKE_RE = re.compile(r"(?:Ã.|Â|â€.|\ufffd)")
FOREIGN_SCRIPT_RE = re.compile(r"[\u0370-\u052f\u0600-\u06ff\u4e00-\u9fff]")
ENGLISH_WORD_RE = re.compile(
    r"\b(?:a|an|and|are|at|by|for|from|in|is|of|on|or|the|to|with|"
    r"will|new|launches|launch|reveals|revealed|returns|first|after|"
    r"before|about|this|that|these|those|car|cars|vehicle|vehicles|"
    r"internet|stranger|owner|owners|tariff|tariffs|tariffa|cost|costs|"
    r"price|prices|sale|sales|plant|plants|factory|factories|update|updates)\b",
    re.IGNORECASE,
)
WHITESPACE_RE = re.compile(r"\s+")
PROMOTIONAL_PHRASES = (
    "hayallerin yeniden",
    "heyecan verici",
    "büyüleyecek",
    "yeni bir soluk",
    "efsanevi otomobil",
    "ambitli",
    "konteyonda",
)


def clean_editorial_text(value: object) -> str:
    """Başlık ve özet alanlarını normalleştirir, görünmez bozuklukları atar."""
    if not isinstance(value, str):
        return ""

    text = repair_mojibake(value)
    text = "".join(
        char for char in text if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )
    return WHITESPACE_RE.sub(" ", text).strip()


def normalize_analysis_result(result: dict[str, object]) -> dict[str, object]:
    """AI analizindeki metin alanlarını kaydetmeden önce temizler."""
    normalized = dict(result)
    for field in ("title_tr", "summary_tr", "brand", "model", "category"):
        normalized[field] = clean_editorial_text(normalized.get(field))
    return normalized


def normalize_instagram_draft(result: dict[str, object]) -> dict[str, object]:
    """Instagram taslağının modelden gelen metin alanlarını temizler."""
    normalized = dict(result)
    for field in (
        "instagram_title",
        "photo_direction",
        "intro",
        "editor_note",
        "question",
        "hashtags",
    ):
        normalized[field] = clean_editorial_text(normalized.get(field))

    details = normalized.get("details")
    if isinstance(details, list):
        normalized["details"] = [clean_editorial_text(item) for item in details]
    return normalized


def _foreign_latin_characters(text: str) -> bool:
    # Q, W ve X model adlarında normaldir. Burada yalnızca Türkçe dışında
    # kullanılan aksanlı/uzatmalı Latin karakterleri hata kabul ediyoruz.
    return any(
        ord(char) > 127
        and "LATIN" in unicodedata.name(char, "")
        and char not in "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"
        and char not in "abcçdefgğhıijklmnoöprsştuüvyz"
        for char in text
    )


def validate_turkish_analysis(result: dict[str, object]) -> list[str]:
    """Yayınlanamayacak kadar bozuk veya İngilizce AI sonuçlarını bildirir."""
    errors: list[str] = []
    title = clean_editorial_text(result.get("title_tr"))
    summary = clean_editorial_text(result.get("summary_tr"))
    combined = f"{title} {summary}".strip()

    if len(title) < 6:
        errors.append("Türkçe başlık çok kısa.")
    if len(summary) < 24:
        errors.append("Türkçe özet çok kısa.")
    if not combined:
        return errors

    if MOJIBAKE_RE.search(combined):
        errors.append("Bozuk karakter dizisi içeriyor.")
    if FOREIGN_SCRIPT_RE.search(combined) or _foreign_latin_characters(combined):
        errors.append("Türkçe alfabesi dışındaki anlamsız karakterleri içeriyor.")

    # Tek bir model adı veya marka İngilizce olabilir; iki ya da daha fazla
    # yaygın İngilizce sözcük metnin Türkçeye çevrilmediğini gösterir.
    if len(ENGLISH_WORD_RE.findall(combined)) >= 2:
        errors.append("Metin yeterince Türkçeleştirilmemiş.")

    return errors


def validate_turkish_instagram_draft(result: dict[str, object]) -> list[str]:
    """Taslakta yabancı dil, bozuk kodlama ve reklam dili kalmadığını doğrular."""
    details = result.get("details")
    detail_text = " ".join(details) if isinstance(details, list) else ""
    fields = (
        result.get("instagram_title"),
        result.get("photo_direction"),
        result.get("intro"),
        detail_text,
        result.get("editor_note"),
        result.get("question"),
    )
    combined = " ".join(clean_editorial_text(value) for value in fields).strip()
    errors: list[str] = []

    if not combined:
        return ["Instagram taslağı metni boş."]
    if MOJIBAKE_RE.search(combined):
        errors.append("Instagram taslağı bozuk karakter dizisi içeriyor.")
    if FOREIGN_SCRIPT_RE.search(combined) or _foreign_latin_characters(combined):
        errors.append("Instagram taslağı Türkçe alfabesi dışı karakter içeriyor.")
    if len(ENGLISH_WORD_RE.findall(combined)) >= 2:
        errors.append("Instagram taslağı yeterince Türkçeleştirilmemiş.")

    lower_text = combined.lower()
    if any(phrase in lower_text for phrase in PROMOTIONAL_PHRASES):
        errors.append("Instagram taslağı nesnel olmayan veya bozuk bir ifade içeriyor.")
    title = clean_editorial_text(result.get("instagram_title"))
    if "!" in title:
        errors.append("Instagram ana başlığı reklam dili içeriyor.")

    return errors
