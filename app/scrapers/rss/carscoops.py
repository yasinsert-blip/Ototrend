from app.scrapers.rss.common import read_rss

def get_carscoops_news():
    return read_rss(
        "https://www.carscoops.com/feed/",
        "Carscoops"
    )