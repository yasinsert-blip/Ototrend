"""OtoTrendTR kurallarına uygun, kaynak fotoğraftan Instagram görseli üretir."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import os
import re
import time
from urllib.parse import urljoin

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
import requests

from app.services.visual_source_service import HTTP_HEADERS, is_public_http_url


CANVAS_SIZE = (1080, 1512)
HEADER_HEIGHT = 270
PHOTO_HEIGHT = 1080
FOOTER_HEIGHT = CANVAS_SIZE[1] - HEADER_HEIGHT - PHOTO_HEIGHT
FOOTER_TEXT = "HABERİN DETAYLARI AÇIKLAMADA"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_REDIRECTS = 3

APP_DIRECTORY = Path(__file__).resolve().parents[1]
STATIC_DIRECTORY = APP_DIRECTORY / "static"
LOGO_PATH = STATIC_DIRECTORY / "images" / "ototrendtr-logo-cutout.png"
OUTPUT_DIRECTORY = (Path(os.environ['OTOTREND_DATA_DIR']) / 'generated' if os.getenv('OTOTREND_DATA_DIR') else STATIC_DIRECTORY / "generated") / "instagram"

FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
)


class VisualRenderError(ValueError):
    """Görselin üretilemediği, editöre gösterilebilecek hata."""


@dataclass(frozen=True)
class RenderedInstagramVisual:
    path: Path
    public_url: str


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_path in FONT_CANDIDATES:
        if font_path.is_file():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default(size=size)


def _download_source_image(image_url: str) -> Image.Image:
    current_url = image_url
    response = None
    try:
        for _ in range(MAX_REDIRECTS + 1):
            if not is_public_http_url(current_url):
                raise VisualRenderError("Görsel kaynağının adresi güvenli değil.")

            response = requests.get(
                current_url,
                headers={
                    **HTTP_HEADERS,
                    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
                },
                timeout=(5, 20),
                stream=True,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                redirect_to = response.headers.get("Location")
                response.close()
                response = None
                if not redirect_to:
                    raise VisualRenderError("Görsel yönlendirme adresi geçersiz.")
                current_url = urljoin(current_url, redirect_to)
                continue

            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and not content_type.startswith("image/"):
                raise VisualRenderError("Kaynak bağlantısı bir görsel dosyası döndürmedi.")

            image_bytes = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                image_bytes.extend(chunk)
                if len(image_bytes) > MAX_IMAGE_BYTES:
                    raise VisualRenderError("Kaynak görsel dosyası çok büyük.")
            break
        else:
            raise VisualRenderError("Görsel kaynağı çok fazla yönlendirme yaptı.")
    except requests.RequestException as exc:
        raise VisualRenderError("Kaynak görsel indirilemedi.") from exc
    finally:
        if response is not None:
            response.close()

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise VisualRenderError("Kaynak dosya geçerli bir görsel değil.") from exc


def _wrap_headline(headline: str) -> tuple[ImageFont.ImageFont, list[str]]:
    clean_headline = re.sub(r"\s+", " ", headline).strip()
    if not clean_headline:
        raise VisualRenderError("Görsel için ana başlık bulunamadı.")

    words = clean_headline.split(" ")
    max_width = CANVAS_SIZE[0] - 80

    for size in range(68, 33, -2):
        font = _font(size)
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and font.getlength(candidate) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)

        line_height = size + 8
        if len(lines) <= 4 and len(lines) * line_height <= 162:
            return font, lines

    # Aşırı uzun başlıklarda tek ana başlık korunur; sığacak biçimde kesilir.
    font = _font(34)
    text = clean_headline[:150].rstrip()
    return font, [text[:58] + ("…" if len(text) > 58 else "")]


def compose_instagram_visual(source_image: Image.Image, headline: str) -> Image.Image:
    """Fotoğrafı değiştirmeden kadrajlayıp sabit OtoTrendTR kimliği uygular."""
    if not LOGO_PATH.is_file():
        raise VisualRenderError("Orijinal OtoTrendTR logo dosyası bulunamadı.")

    canvas = Image.new("RGBA", CANVAS_SIZE, "#101216")
    photo = ImageOps.fit(
        source_image.convert("RGB"),
        (CANVAS_SIZE[0], PHOTO_HEIGHT),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    canvas.alpha_composite(photo.convert("RGBA"), (0, HEADER_HEIGHT))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, CANVAS_SIZE[0], HEADER_HEIGHT), fill="#101216")
    draw.rectangle(
        (0, HEADER_HEIGHT - 4, CANVAS_SIZE[0], HEADER_HEIGHT),
        fill="#e21b23",
    )
    draw.rectangle(
        (0, HEADER_HEIGHT + PHOTO_HEIGHT, CANVAS_SIZE[0], CANVAS_SIZE[1]),
        fill="#101216",
    )

    with Image.open(LOGO_PATH) as original_logo:
        logo = original_logo.convert("RGBA")
        logo.thumbnail((185, 70), Image.Resampling.LANCZOS)
        canvas.alpha_composite(logo, (40, 22))

    title_font, title_lines = _wrap_headline(headline)
    line_height = int(title_font.size * 1.12) if hasattr(title_font, "size") else 42
    title_y = HEADER_HEIGHT - 26 - len(title_lines) * line_height
    for line in title_lines:
        draw.text((40, title_y), line, font=title_font, fill="white")
        title_y += line_height

    footer_font = _font(32)
    footer_box = draw.textbbox((0, 0), FOOTER_TEXT, font=footer_font)
    footer_width = footer_box[2] - footer_box[0]
    footer_height = footer_box[3] - footer_box[1]
    draw.text(
        ((CANVAS_SIZE[0] - footer_width) / 2, HEADER_HEIGHT + PHOTO_HEIGHT + (FOOTER_HEIGHT - footer_height) / 2 - 4),
        FOOTER_TEXT,
        font=footer_font,
        fill="white",
    )
    return canvas


def render_instagram_visual(
    *,
    news_id: int,
    headline: str,
    image_url: str,
) -> RenderedInstagramVisual:
    """Kaynak görseliyle tek başlıklı Instagram JPEG çıktısını kaydeder."""
    if news_id <= 0:
        raise VisualRenderError("Geçersiz haber kaydı.")

    source_image = _download_source_image(image_url)
    visual = compose_instagram_visual(source_image, headline)

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIRECTORY / f"news-{news_id}.jpg"
    visual.convert("RGB").save(
        output_path,
        format="JPEG",
        quality=92,
        optimize=True,
    )
    version = int(time.time())
    return RenderedInstagramVisual(
        path=output_path,
        public_url=f"/static/generated/instagram/{output_path.name}?v={version}",
    )


def rendered_visual_url(news_id: int) -> str | None:
    output_path = OUTPUT_DIRECTORY / f"news-{news_id}.jpg"
    if not output_path.is_file():
        return None
    return f"/static/generated/instagram/{output_path.name}?v={output_path.stat().st_mtime_ns}"
