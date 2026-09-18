from app.scrapers.rss.common import read_rss


def get_drivespark_news():
    return read_rss(
        "https://www.drivespark.com/rss/feeds/drivespark-fb.xml",
        "DriveSpark",
    )
