from app.scrapers.rss.motor1 import get_motor1_news
from app.scrapers.rss.motor1_tr import get_motor1_tr_news
from app.scrapers.rss.carscoops import get_carscoops_news
from app.scrapers.rss.insideevs import get_insideevs_news
from app.scrapers.rss.electrek import get_electrek_news
from app.scrapers.rss.autoblog import get_autoblog_news
from app.scrapers.rss.autoexpress import get_autoexpress_news
from app.scrapers.rss.carbuzz import get_carbuzz_news
from app.scrapers.html.log import get_log_news
from app.scrapers.html.donanimhaber import get_donanimhaber_news
from app.scrapers.html.kolesa import get_kolesa_news
from app.scrapers.rss.cnevpost import get_cnevpost_news

SOURCES = [
    get_motor1_news,
    get_motor1_tr_news,
    get_carscoops_news,
    get_insideevs_news,
    get_electrek_news,
    get_autoblog_news,
    get_autoexpress_news,
    get_log_news,
    get_carbuzz_news,
    get_donanimhaber_news,
    get_kolesa_news
]