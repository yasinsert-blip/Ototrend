import unittest
from app.services.fact_check import check_facts, apply_fact_check
from app.models.news import News


class FactCheckTests(unittest.TestCase):
    def check(self, source, text, **fields):
        return check_facts(source, dict(title_tr=text, **fields))

    def test_translated_price_and_date_match(self):
        self.assertEqual(self.check(
            "Audi Q3 costs $25,000. Orders open September 9, 2026.",
            "Audi Q3 25.000 dolar. Siparişler 9 Eylül 2026 tarihinde.", brand="Audi", model="Q3"
        ), [])

    def test_currency_swap_is_flagged_even_when_number_exists(self):
        self.assertTrue(any("para birimi" in x for x in self.check("Price: $25000", "Fiyat 25000 avro")))

    def test_price_pair_swaps_are_flagged(self):
        self.assertTrue(self.check("US price $25000, Europe EUR 30000", "Avrupa fiyatı 25000 avro"))

    def test_scaled_amount_and_decimal_translation(self):
        self.assertEqual(self.check("Investment: 1.5 billion EUR", "Yatırım 1,5 milyar avro"), [])
        self.assertEqual(self.check("Price: TRY 1500000", "Fiyat 1,5 milyon TL"), [])

    def test_invented_model_brand_and_year(self):
        issues = self.check("Audi Q3 arrives in 2026", "2027 model geliyor", brand="BMW", model="Q5")
        self.assertEqual(len(issues), 3)

    def test_changed_month_is_detected(self):
        self.assertTrue(any("Tarih" in x for x in self.check("September 9, 2026", "9 Ekim 2026")))

    def test_no_claim_does_not_create_warning(self):
        self.assertEqual(self.check("A manufacturer presented a vehicle", "Yeni otomobil tanıtıldı", brand="Unknown", model=""), [])

    def test_suspect_output_is_saved_for_review_not_retry(self):
        news = News(title="Audi Q3", content="Price $25000", status="ai_ready", ai_processed=True)
        self.assertTrue(apply_fact_check(news, dict(title_tr="30000 avro")))
        self.assertEqual(news.status, "editor_review")
        self.assertTrue(news.ai_processed)
        self.assertIn("para birimi", news.fact_check_notes)

    def test_successful_recheck_clears_old_warning(self):
        news = News(title="Audi Q3", content="Price $25000", status="ai_ready", fact_check_notes="old")
        self.assertEqual(apply_fact_check(news, dict(title_tr="25000 dolar", brand="Audi")), [])
        self.assertIsNone(news.fact_check_notes)

    def test_brand_and_model_in_text_are_checked_without_structured_fields(self):
        issues = self.check("Audi Q3 has 5 doors", "BMW Q5 tanıtıldı")
        self.assertTrue(any("marka" in x for x in issues))
        self.assertTrue(any("Model/kod" in x for x in issues))

    def test_warning_prevents_automatic_telegram_notification(self):
        from datetime import UTC, datetime
        from unittest.mock import patch
        from app.services import ai_worker
        news = News(created_at=datetime.now(UTC), telegram_sent=False, fact_check_notes="Fiyat farklı")
        with patch.object(ai_worker, "TELEGRAM_NOTIFY_AFTER", "2020-01-01T00:00:00Z"):
            self.assertFalse(ai_worker._should_send_telegram(news))


if __name__ == "__main__":
    unittest.main()
