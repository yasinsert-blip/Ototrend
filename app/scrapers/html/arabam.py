from app.scrapers.html.common import read_html


def get_arabam_news():
    return read_html(
        url="https://www.arabam.com/blog/haberler/",
        source_name="Arabam",
        article_selector=".tdb_module_loop",
        title_selector=".entry-title a",
        limit=10
    )