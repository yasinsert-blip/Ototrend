from app.scrapers.rss.common import read_rss

def get_motor1_tr_news():
    return read_rss(
        "https://tr.motor1.com/rss/news/all/",
        "Motor1 TR"
    )
