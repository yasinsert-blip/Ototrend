print(">>>>>>>> YENI MOTOR1 DOSYASI CALISTI <<<<<<<<")

from app.scrapers.rss.common import read_rss

def get_motor1_news():
    return read_rss(
        "https://www.motor1.com/rss/news/all/",
        "Motor1"
    )