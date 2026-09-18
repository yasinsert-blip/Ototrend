from app.scrapers.html.common import read_with_fallback


def get_autoevolution_news():
    return read_with_fallback(
        rss_url="https://www.autoevolution.com/rss/backend.xml",
        html_url="https://www.autoevolution.com/",
        source_name="Autoevolution",

        # HTML fallback (gerçek selector'lar doğrulanacak)
        article_selector="article",
        title_selector="h2 a",
        link_selector="h2 a",
        description_selector="p",
        limit=10,
    )
