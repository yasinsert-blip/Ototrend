from app.scrapers.rss.common import read_rss


def get_greencarreports_news():
    return read_rss(
        "https://www.greencarreports.com/rss",
        "GreenCarReports",
    )