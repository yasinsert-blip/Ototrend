from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from email.utils import parsedate_to_datetime


def normalize_date(value):
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except Exception:
        return value


def read_browser(
    url,
    source_name,
    article_selector,
    title_selector,
    link_selector=None,
    description_selector=None,
    date_selector=None,
    author_selector=None,
    limit=10,
    wait_until="networkidle",
    timeout=30000,
):
    """
    Ortak Playwright scraper.

    Dönen veri yapısı RSS ve HTML scraper ile aynıdır.
    """

    print(f"🌍 BROWSER KAYNAĞI: {source_name}")

    news = []

    try:
        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0 Safari/537.36"
                )
            )

            page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout,
            )

            html = page.content()

            browser.close()

    except Exception as e:
        print(f"❌ Browser okunamadı ({source_name}): {e}")
        return []

    soup = BeautifulSoup(html, "lxml")

    articles = soup.select(article_selector)

    print(f"🔍 {source_name}: {len(articles)} article bulundu")

    for article in articles:

        try:

            title_element = article.select_one(title_selector)

            if not title_element:
                continue

            title = title_element.get_text(" ", strip=True)

            if link_selector:
                link_element = article.select_one(link_selector)
            else:
                link_element = title_element

            if not link_element:
                continue

            href = link_element.get("href")

            if not href:
                continue

            link = urljoin(url, href)

            description = None

            if description_selector:
                desc = article.select_one(description_selector)

                if desc:
                    description = desc.get_text(" ", strip=True)

            author = None

            if author_selector:
                author_tag = article.select_one(author_selector)

                if author_tag:
                    author = author_tag.get_text(" ", strip=True)

            published_at = None

            if date_selector:

                date_tag = article.select_one(date_selector)

                if date_tag:

                    published_at = normalize_date(
                        date_tag.get("datetime")
                        or date_tag.get_text(" ", strip=True)
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

    print(f"✅ {source_name}: {len(news)} haber bulundu")

    return news