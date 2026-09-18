import json
import unittest
from unittest.mock import patch

from app.ai.cleaner import clean_text
from app.ai.pipeline import process
from app.ai.turkish_quality import (
    normalize_analysis_result,
    validate_turkish_analysis,
)


class TurkishQualityTests(unittest.TestCase):
    def test_clean_text_repairs_common_mojibake_before_ai_processing(self):
        cleaned = clean_text("Audiâ€™nin TÃ¼rkiyeâ€™deki yeni Q3 tanıtımı")

        self.assertIn("Türkiye", cleaned)
        self.assertNotIn("Ã", cleaned)
        self.assertNotIn("â€", cleaned)

    def test_normalization_repairs_mojibake_in_model_output(self):
        result = normalize_analysis_result(
            {
                "title_tr": "Audiâ€™nin yeni Q3 tanıtımı",
                "summary_tr": "Model TÃ¼rkiye pazarı için tanıtıldı.",
            }
        )

        self.assertEqual(result["title_tr"], "Audi'nin yeni Q3 tanıtımı")
        self.assertIn("Türkiye", result["summary_tr"])

    def test_quality_check_accepts_natural_turkish_with_model_names(self):
        errors = validate_turkish_analysis(
            {
                "title_tr": "Audi Q3'ün yeni tanıtımı yapıldı",
                "summary_tr": "Audi, Q3 modelinin yeni tanıtımını gerçekleştirdi."
                " Marka, teknik ayrıntıları daha sonra paylaşacak.",
            }
        )

        self.assertEqual(errors, [])

    def test_quality_check_rejects_untranslated_or_foreign_output(self):
        errors = validate_turkish_analysis(
            {
                "title_tr": "The new Q3 returns",
                "summary_tr": "The new model returns with a battery update.",
            }
        )

        self.assertTrue(any("Türkçeleştirilmemiş" in error for error in errors))

    def test_quality_check_rejects_english_words_hidden_in_turkish_text(self):
        errors = validate_turkish_analysis(
            {
                "title_tr": "Pontiac Trans Am yeniden gündemde",
                "summary_tr": "Car, internet stranger yardımıyla uzun süreli "
                "restorasyona hazırlanıyor.",
            }
        )

        self.assertTrue(any("Türkçeleştirilmemiş" in error for error in errors))

    def test_pipeline_retries_a_low_quality_draft_once(self):
        invalid = {
            "title_tr": "The new Q3 returns",
            "summary_tr": "The new model returns with a battery update.",
            "brand": "Audi",
            "model": "Q3",
            "category": "SUV",
            "importance": 7,
        }
        valid = {
            "title_tr": "Audi Q3'ün yeni tanıtımı yapıldı",
            "summary_tr": "Audi, Q3 modelinin yeni tanıtımını gerçekleştirdi."
            " Marka, teknik ayrıntıları daha sonra paylaşacak.",
            "brand": "Audi",
            "model": "Q3",
            "category": "SUV",
            "importance": 7,
        }

        with patch(
            "app.ai.pipeline.json_chat",
            side_effect=[json.dumps(invalid), json.dumps(valid, ensure_ascii=False)],
        ) as json_chat:
            result, metrics = process("Audi reveals the new Q3 model.")

        self.assertEqual(result["title_tr"], valid["title_tr"])
        self.assertEqual(json_chat.call_count, 2)
        self.assertEqual(metrics["quality_attempts"], 2)


if __name__ == "__main__":
    unittest.main()
