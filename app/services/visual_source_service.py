"""Haber görsellerini kaynak ve açık lisans bilgisiyle otomatik seçer."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import ipaddress
import json
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.database.database import SessionLocal
from app.models.news import News
from app.models.news_image import NewsImage


REQUEST_TIMEOUT = (5, 10)
MAX_REDIRECTS = 3
WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"
HTTP_HEADERS = {
    "User-Agent": "OtoTrendTR-Newsroom/1.0 (+visual-source-resolver)",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.5",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


@dataclass(frozen=True)
class VisualCandidate:
    image_url: str
    source_url: str
    origin: str
    status: str
    license_name: str | None = None
    license_url: str | None = None
    credit: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "image_url": self.image_url,
            "source_url": self.source_url,
            "origin": self.origin,
            "status": self.status,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "credit": self.credit,
        }


def _clean_text(value: Any) -> str:
    if not value:
        return ""
    return BeautifulSoup(unescape(str(value)), "html.parser").get_text(" ", strip=True)


def is_public_http_url(value: str | None) -> bool:
    """Yalnızca herkese açık HTTP(S) adreslerini kabul eder."""
    if not value or not isinstance(value, str):
        return False

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
        ".local"
    ):
        return False

    # Sayısal adresler için doğrudan kontrol yapılır.
    try:
        return ipaddress.ip_address(hostname).is_global
    except ValueError:
        pass

    # Alan adları dışarıdan geçerli görünse bile iç ağlara yönlenebilir. İstek
    # öncesinde tüm DNS sonuçlarını doğrulayarak SSRF riskini azaltıyoruz.
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    except socket.gaierror:
        return False

    if not addresses:
        return False

    try:
        return all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False


def _get_public_html(url: str) -> str | None:
    """Yönlendirmeleri tek tek doğrulayarak sınırlı bir haber sayfası okur."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_public_http_url(current_url):
            return None
        try:
            response = requests.get(
                current_url,
                headers=HTTP_HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )
        except requests.RequestException:
            return None

        try:
            if response.is_redirect or response.is_permanent_redirect:
                redirect_to = response.headers.get("Location")
                if not redirect_to:
                    return None
                current_url = urljoin(current_url, redirect_to)
                continue

            content_type = response.headers.get("Content-Type", "").lower()
            if response.status_code != 200 or "html" not in content_type:
                return None

            # Görsel aramak için bir haber sayfasında bu boyut yeterlidir.
            return response.text[:1_500_000]
        finally:
            response.close()
    return None


def extract_article_image(html: str, article_url: str) -> str | None:
    """Sayfadaki haber ana görseli için OpenGraph/Twitter/JSON-LD önceliği."""
    if not html or not is_public_http_url(article_url):
        return None

    soup = BeautifulSoup(html, "html.parser")
    for selector, attribute, names in (
        ("meta", "property", ("og:image", "og:image:url")),
        ("meta", "name", ("twitter:image", "twitter:image:src")),
    ):
        for name in names:
            tag = soup.find(selector, attrs={attribute: name})
            if tag and tag.get("content"):
                candidate = urljoin(article_url, tag["content"].strip())
                if is_public_http_url(candidate):
                    return candidate

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(tag.get_text(strip=True))
        except (TypeError, ValueError):
            continue

        for image in _json_ld_images(payload):
            candidate = urljoin(article_url, image)
            if is_public_http_url(candidate):
                return candidate
    return None


def _json_ld_images(payload: Any) -> list[str]:
    """JSON-LD içindeki image alanlarını güvenli biçimde toplar."""
    values: list[str] = []
    queue: list[Any] = [payload]
    while queue:
        item = queue.pop(0)
        if isinstance(item, list):
            queue.extend(item)
        elif isinstance(item, dict):
            image = item.get("image")
            if isinstance(image, str):
                values.append(image)
            elif isinstance(image, dict):
                image_url = image.get("url") or image.get("contentUrl")
                if isinstance(image_url, str):
                    values.append(image_url)
            elif isinstance(image, list):
                queue.extend(image)
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
    return values


def _wikimedia_candidate(query: str) -> VisualCandidate | None:
    """Açık lisans bilgisi bulunan Wikimedia Commons adayını döndürür."""
    if not query.strip():
        return None

    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query[:180],
        "gsrnamespace": "6",
        "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    }
    try:
        response = requests.get(
            WIKIMEDIA_API_URL,
            params=params,
            headers=HTTP_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {}).values()
    except (requests.RequestException, ValueError, AttributeError):
        return None
    finally:
        if "response" in locals():
            response.close()

    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        metadata = info.get("extmetadata") or {}
        license_name = _clean_text(metadata.get("LicenseShortName", {}).get("value"))
        license_url = _clean_text(metadata.get("LicenseUrl", {}).get("value"))
        usage_terms = _clean_text(metadata.get("UsageTerms", {}).get("value"))
        image_url = info.get("url")

        if not is_public_http_url(image_url) or not _is_reusable_license(
            license_name,
            usage_terms,
        ):
            continue

        artist = _clean_text(metadata.get("Artist", {}).get("value"))
        credit = _clean_text(metadata.get("Credit", {}).get("value"))
        attribution = " · ".join(part for part in (artist, credit) if part)
        status = (
            "ready"
            if _is_public_domain(license_name, usage_terms)
            else "attribution_required"
        )
        return VisualCandidate(
            image_url=image_url,
            source_url=info.get("descriptionurl") or "https://commons.wikimedia.org/",
            origin="wikimedia_commons",
            status=status,
            license_name=license_name or usage_terms,
            license_url=license_url or None,
            credit=attribution or None,
        )
    return None


def _is_reusable_license(license_name: str, usage_terms: str) -> bool:
    combined = f"{license_name} {usage_terms}".lower()
    return (
        "public domain" in combined
        or "cc0" in combined
        or "cc by" in combined
    ) and "noncommercial" not in combined and "cc by-nc" not in combined


def _is_public_domain(license_name: str, usage_terms: str) -> bool:
    combined = f"{license_name} {usage_terms}".lower()
    return "public domain" in combined or "cc0" in combined


def _source_candidate(news: News) -> VisualCandidate | None:
    if news.image_url and is_public_http_url(news.image_url):
        return VisualCandidate(
            image_url=news.image_url,
            source_url=news.link,
            origin="feed_image",
            status="review_required",
        )

    if not is_public_http_url(news.link):
        return None
    html = _get_public_html(news.link)
    image_url = extract_article_image(html or "", news.link)
    if not image_url:
        return None
    return VisualCandidate(
        image_url=image_url,
        source_url=news.link,
        origin="article_metadata",
        status="review_required",
    )


def _fallback_query(news: News) -> str:
    return " ".join(
        part.strip()
        for part in (news.brand or "", news.translated_title or news.title or "")
        if part and part.strip()
    )


def resolve_visual_candidate(news: News) -> VisualCandidate | None:
    """Önce kaynak haber görseli, yoksa açık lisanslı internet yedeği."""
    return _source_candidate(news) or _wikimedia_candidate(_fallback_query(news))


def get_selected_visual(news_id: int) -> NewsImage | None:
    db = SessionLocal()
    try:
        return (
            db.query(NewsImage)
            .filter(
                NewsImage.news_id == news_id,
                NewsImage.is_selected.is_(True),
            )
            .order_by(NewsImage.id.desc())
            .first()
        )
    finally:
        db.close()


def resolve_and_save_visual(news: News) -> NewsImage | None:
    """Adayı bir kez seçer; daha önce seçilmiş görseli tekrar aramaz."""
    existing = get_selected_visual(news.id)
    if existing:
        return existing

    candidate = resolve_visual_candidate(news)
    if not candidate:
        return None

    db = SessionLocal()
    try:
        db.query(NewsImage).filter(
            NewsImage.news_id == news.id,
            NewsImage.is_selected.is_(True),
        ).update({NewsImage.is_selected: False}, synchronize_session=False)

        image = NewsImage(news_id=news.id, is_selected=True, **candidate.as_dict())
        db.add(image)

        persisted_news = db.query(News).filter(News.id == news.id).first()
        if persisted_news:
            persisted_news.image_url = candidate.image_url
            persisted_news.cover_image = candidate.image_url

        db.commit()
        db.refresh(image)
        return image
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def visual_for_response(image: NewsImage | None) -> dict[str, str | None]:
    if image is None:
        return {
            "status": "not_found",
            "message": (
                "Kaynak sayfada görsel bulunamadı; açık lisanslı yedek görsel de "
                "eşleşmedi. Görselsiz taslak yayınlanamaz."
            ),
            "image_url": None,
            "source_url": None,
            "origin": None,
            "license_name": None,
            "license_url": None,
            "credit": None,
        }

    messages = {
        "ready": "Açık lisanslı görsel otomatik seçildi; yayın için hazır.",
        "attribution_required": (
            "Açık lisanslı görsel otomatik seçildi; yayın öncesi lisans atfını ekleyin."
        ),
        "review_required": (
            "Haber kaynağındaki görsel otomatik seçildi; kullanım izni/lisansını "
            "yayın öncesi doğrulayın."
        ),
    }
    return {
        "status": image.status,
        "message": messages.get(image.status, "Görsel kaynağı kontrol bekliyor."),
        "image_url": image.image_url,
        "source_url": image.source_url,
        "origin": image.origin,
        "license_name": image.license_name,
        "license_url": image.license_url,
        "credit": image.credit,
    }
