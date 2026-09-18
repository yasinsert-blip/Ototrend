from app.scrapers.html.common import read_html


def get_kolesa_news():
    return read_html(
        url="https://www.kolesa.ru/news",
        source_name="Kolesa",
        article_selector="a.post-list-item",
        title_selector=".post-name",
        limit=10
    )