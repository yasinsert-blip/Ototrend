from app.scrapers.html.common import read_html


def get_donanimhaber_news():

    return read_html(
        url="https://www.donanimhaber.com/otomobil",
        source_name="DonanımHaber",
        article_selector="article",
        title_selector="h2 a, h3 a"
    )