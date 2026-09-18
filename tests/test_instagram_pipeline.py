import json
import unittest
from datetime import datetime
from unittest.mock import patch

from app.ai.instagram_pipeline import process_instagram


class InstagramPipelineTests(unittest.TestCase):
    def test_composes_required_caption_sections_from_model_fields(self):
        model_draft = {
            "instagram_title": "Yeni Elektrikli Model Tanıtıldı",
            "photo_direction": "Aracın ön üç çeyrek görünümünü öne çıkar.",
            "intro": "Marka yeni elektrikli modelini duyurdu.",
            "details": [
                "Yeni modelin tanıtımı yapıldı.",
                "Araç elektrikli altyapı kullanıyor.",
                "Marka teknik ayrıntıları paylaştı.",
                "Haber resmi açıklamaya dayanıyor.",
            ],
            "editor_note": "Açıklama, markanın paylaştığı bilgilerle sınırlı.",
            "question": "Yeni modeli nasıl buldunuz",
            "hashtags": "#ElektrikliArac #OtoTrendTR",
            "validation_notes": [],
        }

        with patch(
            "app.ai.instagram_pipeline.instagram_chat",
            return_value=json.dumps(model_draft, ensure_ascii=False),
        ):
            draft, _ = process_instagram(
                "Marka yeni elektrikli modelini duyurdu. Araç elektrikli "
                "altyapı kullanıyor. Marka teknik ayrıntıları paylaştı.",
                source_name="Resmi Marka",
                published_at=datetime(2026, 8, 15),
                headline="Yeni Elektrikli Model Tanıtıldı",
            )

        self.assertIn("📊 ÖNE ÇIKAN DİKKAT ÇEKİCİ DETAYLAR:", draft["instagram_caption"])
        self.assertEqual(draft["instagram_caption"].count("🔹 "), 4)
        self.assertIn("💡 EDİTÖR NOTU:", draft["instagram_caption"])
        self.assertIn("Yorumlarda buluşalım! 👇", draft["instagram_caption"])
        self.assertIn("⚠️ Bilgilendirme: Reklam değildir.", draft["instagram_caption"])
        self.assertIn("📍 KAYNAKLAR: Resmi Marka (Ağustos 2026)", draft["instagram_caption"])
        self.assertIn("#OtoTrendTR", draft["hashtags"])

    def test_retries_a_promotional_or_untranslated_draft(self):
        invalid_draft = {
            "instagram_title": "Restorasyon Heyecanı!",
            "photo_direction": "Aracı öne çıkar.",
            "intro": "Hayallerin yeniden canlanacağı heyecan verici proje başlıyor.",
            "details": [
                "Car, internet stranger yardımıyla hazırlanıyor.",
                "Ambitli hedef restorasyonu tamamlamak.",
                "Araç uzun süredir bekliyor.",
                "Proje tutkunları büyüleyecek.",
            ],
            "editor_note": "Proje restorasyona yeni bir soluk getirecek.",
            "question": "Bu aracı nasıl buldunuz",
            "hashtags": "#OtoTrendTR",
            "validation_notes": [],
        }
        valid_draft = {
            "instagram_title": "Klasik Model İçin Restorasyon Başladı",
            "photo_direction": "Aracın özgün dış görünümünü koruyan geniş kadraj.",
            "intro": "Klasik model için restorasyon süreci başlatıldı.",
            "details": [
                "Araç uzun süredir kullanılmadan bekliyordu.",
                "Restorasyon süreci kaynak haberde açıklandı.",
                "Çalışmada aracın özgün ayrıntılarının korunması hedefleniyor.",
                "Teknik gelişmeler ilerleyen aşamada paylaşılacak.",
            ],
            "editor_note": "Açıklama, kaynak haberde yer alan bilgilerle sınırlıdır.",
            "question": "Klasik otomobil restorasyonları hakkında ne düşünüyorsunuz",
            "hashtags": "#KlasikOtomobil #OtoTrendTR",
            "validation_notes": [],
        }

        with patch(
            "app.ai.instagram_pipeline.instagram_chat",
            side_effect=[
                json.dumps(invalid_draft, ensure_ascii=False),
                json.dumps(valid_draft, ensure_ascii=False),
            ],
        ) as instagram_chat:
            draft, metrics = process_instagram(
                "Klasik model uzun süredir bekliyordu. Restorasyon süreci başlatıldı.",
                source_name="Test Kaynak",
                published_at=datetime(2026, 8, 15),
                headline="Klasik Model İçin Restorasyon Başladı",
            )

        self.assertEqual(instagram_chat.call_count, 2)
        self.assertEqual(metrics["quality_attempts"], 2)
        self.assertEqual(draft["instagram_title"], valid_draft["instagram_title"])
        self.assertNotIn("heyecan verici", draft["instagram_caption"].lower())


if __name__ == "__main__":
    unittest.main()
