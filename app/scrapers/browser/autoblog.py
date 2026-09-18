from app.scrapers.browser.common import read_browser

SCRAPER_NAME = "Autoblog"
SCRAPER_TYPE = "browser"


def get_autoblog_news():
    """
    Autoblog Browser Scraper
    DataDome koruması nedeniyle Playwright kullanır.
    """

    return read_browser(
        url="https://www.autoblog.com/",

        source_name="Autoblog",

        article_selector="article",

        title_selector="h2 a",

        link_selector="h2 a",

        description_selector="p",

        limit=10,
    )