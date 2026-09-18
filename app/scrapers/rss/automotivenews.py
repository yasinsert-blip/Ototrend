from app.scrapers.rss.common import read_rss


def get_automotivenews_news():
    return read_rss(
        url="https://feeds.feedburner.com/autonews/BreakingNews",
        source_name="AutomotiveNews",
        limit=10,
    )
