import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.services import instagram_visual_service


class InstagramVisualServiceTests(unittest.TestCase):
    def test_composed_visual_has_required_instagram_dimensions(self):
        source = Image.new("RGB", (1600, 900), "#2465a5")

        visual = instagram_visual_service.compose_instagram_visual(
            source,
            "YENİ MODEL TÜRKİYE YOLUNDA",
        )

        self.assertEqual(visual.size, (1080, 1512))
        self.assertEqual(visual.mode, "RGBA")

    def test_render_saves_a_jpeg_with_a_public_static_url(self):
        source = Image.new("RGB", (1600, 900), "#2465a5")
        with tempfile.TemporaryDirectory() as temp_directory, patch.object(
            instagram_visual_service,
            "OUTPUT_DIRECTORY",
            Path(temp_directory),
        ), patch.object(
            instagram_visual_service,
            "_download_source_image",
            return_value=source,
        ):
            rendered = instagram_visual_service.render_instagram_visual(
                news_id=42,
                headline="YENİ MODEL TÜRKİYE YOLUNDA",
                image_url="https://images.example.com/car.jpg",
            )

            self.assertTrue(rendered.path.is_file())
            self.assertIn("/static/generated/instagram/news-42.jpg", rendered.public_url)
            with Image.open(rendered.path) as image:
                self.assertEqual(image.size, (1080, 1512))
                self.assertEqual(image.format, "JPEG")


if __name__ == "__main__":
    unittest.main()
