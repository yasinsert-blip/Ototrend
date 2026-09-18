from app.scrapers.html.common import read_html


def get_autoexpress_news():
    return read_html(
        url="https://www.autoexpress.co.uk/",
        source_name="AutoExpress",

        # Yeni Polaris tasarımı
        article_selector=".polaris__article-card",

        # Başlık
        title_selector=".polaris__article-card--title",

        # Link
        link_selector="a.polaris__article-card--link",

        # Özet
        description_selector=".polaris__article-card--excerpt",

        # Tarih
        date_selector=".polaris__article-card--date",

        limit=10,
    )