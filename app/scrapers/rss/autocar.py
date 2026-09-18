from app.scrapers.html.common import read_with_fallback


def get_autocar_news():
    return read_with_fallback(
        rss_url="https://www.autocar.co.uk/rss",
        html_url="https://www.autocar.co.uk/",
        source_name="Autocar",

        # HTML fallback (doğrulanacak)
        article_selector="article",
        title_selector="h3 a",
        link_selector="h3 a",
        description_selector="p",
        limit=10,
    )