from app.scrapers.rss.common import read_rss


def get_autocarindia_news():
    return read_rss(
        "https://www.autocarindia.com/rss/all",
        "AutocarIndia",
    )
