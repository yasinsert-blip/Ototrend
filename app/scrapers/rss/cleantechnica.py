from app.scrapers.rss.common import read_rss


def get_cleantechnica_news():
    return read_rss(
        "https://cleantechnica.com/feed/",
        "CleanTechnica",
    )