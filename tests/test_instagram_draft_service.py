import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import instagram_draft_service


class InstagramDraftServiceTests(unittest.TestCase):
    def test_draft_is_persisted_and_visual_is_returned(self):
        news = SimpleNamespace(
            id=42,
            content=(
                "Üretici yeni elektrikli otomobilin Avrupa pazarına yönelik üretim planlarını açıkladı. "
                "Fabrikada gelecek yıl başlayacak üretim için ek çalışanlar alınacak ve mevcut tesisler yenilenecek. "
                "Şirket batarya kapasitesi, şarj altyapısı, servis hizmetleri ve bayi eğitimleri hakkında bilgi verdi. "
                "Fiyatlar ile teslimat tarihleri siparişler açılmadan önce her ülke için ayrıca duyurulacak."
            ),
            summary=None,
            translated_title="Test başlık",
            title="Test başlık",
            source="Test Kaynak",
            published_at=None,
            created_at=None,
        )
        image = SimpleNamespace(image_url="https://images.example.test/car.jpg")
        result = {
            "instagram_title": "YENİ MODEL GELİYOR",
            "instagram_caption": "Açıklama metni",
            "hashtags": "#OtoTrendTR",
            "image_prompt": "Kaynak fotoğrafı",
        }

        with patch.object(instagram_draft_service, "get_news_by_id", return_value=news), patch.object(
            instagram_draft_service,
            "resolve_and_save_visual",
            return_value=image,
        ), patch.object(
            instagram_draft_service,
            "visual_for_response",
            return_value={"message": "Kaynak fotoğrafı seçildi."},
        ), patch.object(
            instagram_draft_service,
            "process_instagram",
            return_value=(result, {"duration": 1}),
        ), patch.object(
            instagram_draft_service,
            "update_instagram_content",
        ) as update, patch.object(
            instagram_draft_service,
            "render_instagram_visual",
            return_value=SimpleNamespace(public_url="/static/generated/instagram/news-42.jpg"),
        ):
            progress_updates = []
            draft = instagram_draft_service.create_instagram_draft(
                42,
                report_progress=lambda progress, message: progress_updates.append(
                    (progress, message)
                ),
            )

        self.assertEqual(draft["news_id"], 42)
        self.assertEqual(draft["data"]["instagram_title"], result["instagram_title"])
        self.assertEqual(draft["data"]["generated_image"], "/static/generated/instagram/news-42.jpg")
        update.assert_called_once()
        self.assertEqual(
            [progress for progress, _ in progress_updates],
            [10, 22, 38, 72, 84, 100],
        )

    def test_missing_news_raises_not_found_error(self):
        with patch.object(instagram_draft_service, "get_news_by_id", return_value=None):
            with self.assertRaises(LookupError):
                instagram_draft_service.create_instagram_draft(404)

    def test_headline_only_never_calls_model_or_image_lookup(self):
        news = SimpleNamespace(title="Yeni otomobil tanıtıldı", content="Yeni otomobil tanıtıldı")
        with patch.object(instagram_draft_service, "get_news_by_id", return_value=news), patch.object(
            instagram_draft_service, "process_instagram"
        ) as model, patch.object(instagram_draft_service, "resolve_and_save_visual") as images:
            with self.assertRaises(instagram_draft_service.InstagramDraftError):
                instagram_draft_service.create_instagram_draft(1)
            model.assert_not_called()
            images.assert_not_called()


if __name__ == "__main__":
    unittest.main()
