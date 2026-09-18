"""Haber kaynaklarını güvenli ve verimli biçimde tarama servisi."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit, urlunsplit

from app.config import RSS_FETCH_WORKERS
from app.database.crud import save_news
from app.database.source_crud import (
    mark_source_error,
    mark_source_run,
    mark_source_success,
)
from app.scrapers.registry import get_scraper_function, get_scraper_type
from app.services.source_service import get_enabled_sources


# Zamanlayıcı ve panelden gelen eşzamanlı istekler aynı kaynakları ikinci kez
# taramaya başlamamalıdır. Kilit, çalışan tur bitene kadar yeni turu atlar.
_news_scan_lock = Lock()


def _normalize_rss_url(value: str | None) -> str:
    """Aynı RSS adresinin küçük yazım farklarıyla tekrar taranmasını önler."""

    if not value or not value.strip():
        return ""

    parts = urlsplit(value.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            parts.query,
            "",
        )
    )


def _mark_group_error(sources, message: str) -> None:
    """Aynı feed'i kullanan kaynaklara aynı bağlantı sonucunu işler."""

    for source in sources:
        auto_disabled = mark_source_error(source.name, message)
        print(f"❌ Kaynak: {source.name} | {message}")
        if auto_disabled:
            print(f"🛑 Kaynak otomatik pasife alındı: {source.name}")


def _mark_group_success(sources, new_count: int) -> None:
    """İçerik tek kez kaydedilir; diğer aynı-feed kayıtları başarılı sayılır."""

    for index, source in enumerate(sources):
        mark_source_success(source.name, new_count if index == 0 else 0)


def _fetch_generic_rss(scraper, source):
    return scraper(
        url=source.rss_url,
        source_name=source.name,
        raise_on_error=True,
    )


def _scan_generic_rss(sources) -> int:
    """Genel RSS kaynaklarını sınırlı paralellikle, tekrarsız indirir."""

    groups: dict[str, list] = {}
    for source in sources:
        groups.setdefault(_normalize_rss_url(source.rss_url), []).append(source)

    scraper = get_scraper_function("RSS")
    if scraper is None:
        for group in groups.values():
            _mark_group_error(group, "Scraper bulunamadı: RSS")
        return 0

    total_new = 0
    futures = {}

    with ThreadPoolExecutor(max_workers=RSS_FETCH_WORKERS) as executor:
        for url_key, group in groups.items():
            for source in group:
                mark_source_run(source.name)

            source = group[0]
            if not url_key:
                _mark_group_error(group, "RSS adresi eksik")
                continue

            alias_note = (
                f" | {len(group)} aynı adres" if len(group) > 1 else ""
            )
            print(f"▶ {source.name} [rss]{alias_note}")
            futures[executor.submit(_fetch_generic_rss, scraper, source)] = group

        for future in as_completed(futures):
            group = futures[future]
            source = group[0]
            try:
                news = future.result()
                new_news = save_news(news)
            except Exception as error:
                _mark_group_error(group, str(error))
                continue

            _mark_group_success(group, len(new_news))
            alias_note = f" ({len(group)} kaynak ortak)" if len(group) > 1 else ""
            print(f"✅ {source.name:<25}{len(new_news)} yeni haber{alias_note}")
            total_new += len(new_news)

    return total_new


def _scan_special_source(source) -> int:
    """Kendine özgü HTML veya tarayıcı kaynaklarını sıralı olarak tarar."""

    mark_source_run(source.name)
    scraper = get_scraper_function(source.scraper)

    if scraper is None:
        message = f"Scraper bulunamadı: {source.scraper}"
        _mark_group_error([source], message)
        return 0

    scraper_type = get_scraper_type(source.scraper)
    print(f"▶ {source.name} [{scraper_type}]")

    try:
        news = scraper()
        new_news = save_news(news)
    except Exception as error:
        _mark_group_error([source], str(error))
        return 0

    mark_source_success(source.name, len(new_news))
    print(f"✅ {source.name:<25}{len(new_news)} yeni haber")
    return len(new_news)


def update_news() -> int | None:
    """Etkin kaynakları bir kez tarar; aynı anda ikinci turu başlatmaz."""

    if not _news_scan_lock.acquire(blocking=False):
        print("⏭ Haber taraması zaten çalışıyor; ikinci tur atlandı.")
        return None

    started_at = monotonic()
    try:
        print("=" * 60)
        print("🚗 Haber taraması başladı...\n")

        sources = get_enabled_sources()
        print(f"Toplam aktif kaynak: {len(sources)}")

        if not sources:
            print("⚠ Aktif kaynak bulunamadı.")
            print("=" * 60)
            return 0

        generic_rss = [source for source in sources if source.scraper == "RSS"]
        special_sources = [source for source in sources if source.scraper != "RSS"]

        total_new = _scan_generic_rss(generic_rss)
        for source in special_sources:
            total_new += _scan_special_source(source)

        elapsed = monotonic() - started_at
        print("\n----------------------------------------")
        print(f"🆕 Toplam yeni haber: {total_new}")
        print(f"⏱ Tarama süresi: {elapsed:.1f} saniye")
        print("✔ Haber taraması tamamlandı")
        print("=" * 60)
        return total_new
    finally:
        _news_scan_lock.release()
