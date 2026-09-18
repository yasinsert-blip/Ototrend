import requests

from app.scrapers.rss.common import read_rss

from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0 Safari/537.36"
)

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/",
}

session = requests.Session()
session.headers.update(REQUEST_HEADERS)


def normalize_date(value):
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except Exception:
        return value


def read_html(
    url,
    source_name,
    article_selector,
    title_selector,
    link_selector=None,
    description_selector=None,
    date_selector=None,
    author_selector=None,
    limit=10,
    verify=True,
):
    """
    Ortak HTML scraper.

    Dönen veri yapısı RSS scraper ile tamamen uyumludur.
    """

    print(f"📄 OKUNAN HTML KAYNAK: {source_name}")

    try:
        response = session.get(
            url,
            timeout=(10, 30),
            allow_redirects=True,
            verify=verify,
        )

        print(f"🌐 HTTP {response.status_code} ({source_name})")

        if response.history:
            print(f"↪ Redirect: {response.url}")

        response.raise_for_status()

        print("Encoding:", response.encoding)
        print("Content-Encoding:", response.headers.get("Content-Encoding"))
        print("Content-Type:", response.headers.get("Content-Type"))

    except requests.exceptions.RequestException as e:
        print(f"❌ HTML okunamadı ({source_name}): {e}")
        return []

    try:
        soup = BeautifulSoup(response.text, "lxml")
    except Exception:
        soup = BeautifulSoup(response.text, "html.parser")

    articles = soup.select(article_selector)

    print(f"🔍 {source_name}: {len(articles)} article bulundu")

    if not articles:
        print(f"⚠ Haber bulunamadı ({source_name})")
        return []

    news = []

    for article in articles:

        try:
            title_element = article.select_one(title_selector)

            if not title_element:
                continue

            title = title_element.get_text(" ", strip=True)

            # Link
            if link_selector:
                link_element = article.select_one(link_selector)
            else:
                link_element = title_element

            link = None

            if link_element:

                if link_element.has_attr("href"):
                    link = link_element["href"]

                else:
                    parent = link_element.find_parent("a")

                    if parent and parent.has_attr("href"):
                        link = parent["href"]

            if not link:
                continue

            link = urljoin(url, link)

            # Description
            description = None

            if description_selector:

                desc = article.select_one(description_selector)

                if desc:
                    description = desc.get_text(" ", strip=True)

            # Author
            author = None

            if author_selector:

                author_element = article.select_one(author_selector)

                if author_element:
                    author = author_element.get_text(" ", strip=True)

            # Published Date
            published_at = None

            if date_selector:

                date_element = article.select_one(date_selector)

                if date_element:

                    published_at = normalize_date(
                        date_element.get("datetime")
                        or date_element.get_text(" ", strip=True)
                    )

            news.append(
                {
                    "title": title,
                    "description": description,
                    "content": description,
                    "link": link,
                    "source": source_name,
                    "author": author,
                    "published_at": published_at,
                    "language": None,
                }
            )

            if len(news) >= limit:
                break

        except Exception as e:
            print(f"⚠ Haber işlenemedi ({source_name}): {e}")
            continue

    print(f"✅ {source_name}: {len(news)} haber bulundu")

    return news


def read_with_fallback(
    rss_url,
    html_url,
    source_name,
    article_selector,
    title_selector,
    link_selector=None,
    description_selector=None,
    date_selector=None,
    author_selector=None,
    limit=10,
):
    """
    Önce RSS'i dener.
    RSS başarısız olursa otomatik olarak HTML scraper'a geçer.
    """

    print("=" * 70)
    print(f"📰 KAYNAK : {source_name}")
    print(f"📡 RSS    : {rss_url}")
    print(f"🌐 HTML   : {html_url}")
    print("=" * 70)

    try:
        news = read_rss(
            rss_url,
            source_name,
            limit=limit,
        )

        print(f"📊 RSS Haber Sayısı: {len(news)}")

        if news:
            print(f"✅ {source_name}: RSS kullanıldı ({len(news)} haber)")
            print("=" * 70)
            return news

        print(f"⚠ {source_name}: RSS boş liste döndürdü.")

    except Exception as e:
        print(f"❌ RSS Exception ({source_name})")
        print(type(e).__name__)
        print(e)

    print(f"➡ HTML Fallback başlatılıyor ({source_name})")
    print("=" * 70)

    news = read_html(
        url=html_url,
        source_name=source_name,
        article_selector=article_selector,
        title_selector=title_selector,
        link_selector=link_selector,
        description_selector=description_selector,
        date_selector=date_selector,
        author_selector=author_selector,
        limit=limit,
    )

    print(f"📊 HTML Haber Sayısı: {len(news)}")
    print("=" * 70)

    return news