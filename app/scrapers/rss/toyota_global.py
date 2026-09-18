from app.scrapers.html.common import read_with_fallback


def get_toyota_global_news():
    return read_with_fallback(
        rss_url="https://global.toyota/export/en/allnews_rss.xml",
        html_url="https://global.toyota/en/newsroom/",
        source_name="Toyota Global Newsroom",
        article_selector="article",
        title_selector="h3 a",
        link_selector="h3 a",
        description_selector="p",
    )
