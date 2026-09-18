"""Read-only discovery of feed links and current entries; never changes the DB."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import feedparser
import requests


def probe(url):
    result = {"url": url}
    try:
        with requests.get(url, headers={"User-Agent": "OtoTrendFeedCheck/1.0", "Accept": "application/rss+xml, application/atom+xml, text/html;q=0.8"}, timeout=(10, 25)) as response:
            result.update(status=response.status_code, final_url=response.url,
                          content_type=response.headers.get("Content-Type"))
            if response.status_code != 200:
                return result
            parsed = feedparser.parse(response.content)
            if parsed.version and parsed.entries:
                result.update(feed_title=parsed.feed.get("title"), entries=len(parsed.entries),
                              version=parsed.version, bozo=bool(parsed.bozo),
                              examples=[dict(title=row.get("title"), link=row.get("link"),
                                             published=row.get("published"), source=row.get("source"),
                                             summary=BeautifulSoup(row.get("summary", ""), "html.parser").get_text(" ", strip=True)[:500])
                                        for row in parsed.entries[:5]])
            else:
                soup = BeautifulSoup(response.content, "html.parser")
                result["title"] = soup.title.get_text() if soup.title else None
                result["feed_links"] = [dict(title=link.get("title"), href=urljoin(response.url, link["href"]))
                                        for link in soup.find_all("link", href=True)
                                        if link.get("type") in {"application/rss+xml", "application/atom+xml"}]
                result["rss_links"] = [urljoin(response.url, a["href"]) for a in soup.find_all("a", href=True)
                                       if "rss" in a["href"].lower() or "rss" in a.get_text().lower()][:12]
    except requests.RequestException as error:
        result["error"] = str(error)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(probe, args.urls))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(dict(checked_at=datetime.now(timezone.utc).isoformat(), results=results), ensure_ascii=False, indent=2), encoding="utf-8")
