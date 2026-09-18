from app.scrapers.rss.common import read_rss


def get_cnevpost_news():
    return read_rss(
        url="https://cnevpost.com/feed/",
        source_name="CNEVPost",
        limit=10,
    )