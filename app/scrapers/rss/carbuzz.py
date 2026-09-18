from app.scrapers.rss.common import read_rss

def get_carbuzz_news():
    return read_rss(
        "https://carbuzz.com/feed/"
        ,
        "CarBuzz"
    )