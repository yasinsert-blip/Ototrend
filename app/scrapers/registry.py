"""
OtoTrend AI Newsroom
Scraper Registry

RSS / HTML / Browser scraper'larının ortak erişim katmanı.
"""

from app.scrapers.auto_registry import (
    SCRAPER_REGISTRY,
    get_scraper,
    get_scraper_info,
    get_scraper_names,
    get_all_scrapers,
)


def get_scraper_function(name: str):
    """
    Scraper fonksiyonunu döndürür.
    """

    return get_scraper(name)


def get_scraper_type(name: str):
    """
    rss / html / browser
    """

    info = get_scraper_info(name)

    if info:
        return info["type"]

    return None


def get_scraper_folder(name: str):
    """
    rss / html / browser klasörü
    """

    info = get_scraper_info(name)

    if info:
        return info["folder"]

    return None


def get_scraper_module(name: str):
    """
    Python modül yolu
    """

    info = get_scraper_info(name)

    if info:
        return info["module"]

    return None


def scraper_exists(name: str):
    """
    Registry'de kayıtlı mı?
    """

    return name in SCRAPER_REGISTRY


def list_scrapers():
    """
    Tüm scraper isimleri
    """

    return get_scraper_names()


def list_scraper_infos():
    """
    Tüm scraper bilgileri
    """

    return get_all_scrapers()


def print_registry():

    print("\n" + "=" * 80)
    print("AUTO SCRAPER REGISTRY")
    print("=" * 80)

    print(f"Toplam Scraper : {len(SCRAPER_REGISTRY)}")

    print("-" * 80)

    for name in sorted(SCRAPER_REGISTRY):

        item = SCRAPER_REGISTRY[name]

        print(
            f"{item['name']:<22}"
            f"{item['type']:<10}"
            f"{item['module']}"
        )

    print("=" * 80)


if __name__ == "__main__":
    print_registry()