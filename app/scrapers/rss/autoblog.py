from app.scrapers.html.common import read_with_fallback


SCRAPER_NAME = "Autoblog"


def get_autoblog_news():
    print("=" * 60)
    print("🚗 AUTOBLOG SCRAPER")
    print("=" * 60)

    rss_url = "https://www.autoblog.com/rss.xml"
    html_url = "https://www.autoblog.com/"

    print(f"RSS URL  : {rss_url}")
    print(f"HTML URL : {html_url}")

    news = read_with_fallback(
        rss_url=rss_url,
        html_url=html_url,
        source_name="Autoblog",
        article_selector="article",
        title_selector="h2 a",
        link_selector="h2 a",
        description_selector="p",
        limit=10,
    )

    print(f"Toplam Haber : {len(news)}")
    print("=" * 60)

    return news