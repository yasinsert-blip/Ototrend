from app.scrapers.rss.common import read_rss


def get_insideevs_news():
    return read_rss(
        "https://insideevs.com/rss/articles/all/",
        "InsideEVs",
    )