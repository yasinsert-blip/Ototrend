import re
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import feedparser
import requests


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0 Safari/537.36"
)

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "application/rss+xml, "
        "application/xml;q=0.9, "
        "text/xml;q=0.8, "
        "*/*;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


session = requests.Session()
session.headers.update(REQUEST_HEADERS)


def clean_html(text):
    if not text:
        return None

    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def normalize_date(value):
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except Exception:
        return value


def _feed_image_url(item, base_url):
    """RSS/Media RSS içindeki haber ana görselini bulur."""
    candidates = []

    for media_item in item.get("media_content", []) or []:
        if isinstance(media_item, dict):
            candidates.append(media_item.get("url"))

    for media_item in item.get("media_thumbnail", []) or []:
        if isinstance(media_item, dict):
            candidates.append(media_item.get("url"))

    for enclosure in item.get("enclosures", []) or []:
        if not isinstance(enclosure, dict):
            continue
        media_type = (enclosure.get("type") or "").lower()
        if media_type.startswith("image/"):
            candidates.append(enclosure.get("href") or enclosure.get("url"))

    image = item.get("image")
    if isinstance(image, dict):
        candidates.append(image.get("href") or image.get("url"))
    elif isinstance(image, str):
        candidates.append(image)

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return urljoin(base_url, candidate.strip())

    return None


def read_rss(
    url,
    source_name,
    limit=10,
    verify=True,
    raise_on_error=False,
):

    print(f"📡 OKUNAN KAYNAK: {source_name}")

    if not url or not url.strip():
        print(f"⏭ RSS adresi yok ({source_name})")
        return []

    try:
        response = session.get(
            url,
            timeout=(10, 30),
            verify=verify,
            allow_redirects=True,
        )

        print(f"🌐 HTTP {response.status_code} ({source_name})")

        if response.history:
            print(f"↪ Redirect -> {response.url}")

        response.raise_for_status()

        feed = feedparser.parse(response.content)

    except requests.exceptions.RequestException as e:
        print(f"❌ RSS okunamadı ({source_name}): {e}")
        if raise_on_error:
            raise
        return []

    except Exception as e:
        print(f"❌ RSS parse hatası ({source_name}): {e}")
        if raise_on_error:
            raise
        return []

    if getattr(feed, "bozo", False):
        print(f"⚠ RSS parse uyarısı: {source_name}")

    print(f"📰 {source_name}: {len(feed.entries)} haber bulundu")

    news = []

    for item in feed.entries[:limit]:

        content = None

        if hasattr(item, "content") and item.content:
            content = item.content[0].value

        elif item.get("summary"):
            content = item.get("summary")

        news.append(
            {
                "title": item.get("title"),
                "description": clean_html(item.get("summary")),
                "content": clean_html(content),
                "link": item.get("link"),
                "source": source_name,
                "author": item.get("author"),
                "image_url": _feed_image_url(item, url),
                "published_at": normalize_date(item.get("published")),
                "language": feed.feed.get("language"),
            }
        )

    return news
