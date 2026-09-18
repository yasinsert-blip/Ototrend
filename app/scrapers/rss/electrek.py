from app.scrapers.rss.common import read_rss

def get_electrek_news():
    return read_rss(
        "https://electrek.co/feed/",
        "Electrek"
    )