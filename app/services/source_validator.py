"""Kaynak formları ve kaynak sağlığı için ortak yapılandırma denetimi."""

from urllib.parse import urlsplit

from app.scrapers.registry import scraper_exists


def valid_web_address(value: str) -> bool:
    try:
        parts = urlsplit(value)
        return (
            parts.scheme in {"http", "https"} and bool(parts.hostname)
            and not parts.username and not parts.password
            and (parts.port is None or 1 <= parts.port <= 65535)
        )
    except ValueError:
        return False


def validate(source):
    errors = []
    if not (source.name or "").strip() or len(source.name.strip()) > 100:
        errors.append("Kaynak adı 1–100 karakter olmalı.")
    if not scraper_exists(source.scraper):
        errors.append("Kaynak okuyucusu bulunamadı; listeden bir okuyucu seçin.")
    if source.scraper == "RSS" and not (source.rss_url or "").strip():
        errors.append("Genel RSS okuyucusu için RSS adresi gerekli.")
    for label, value in (("RSS", source.rss_url), ("Web sitesi", source.website)):
        if value and not valid_web_address(value):
            errors.append(f"{label} adresi http:// veya https:// ile başlayan geçerli bir adres olmalı.")
    if not 1 <= int(source.priority or 0) <= 100:
        errors.append("Öncelik 1–100 arasında olmalı.")
    return errors
