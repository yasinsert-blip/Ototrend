import unittest
from app.services.news_value import evaluate_news_value


class NewsValueTests(unittest.TestCase):
    def test_turkey_price_has_priority_over_generic_launch(self):
        local, reason = evaluate_news_value("Toyota Türkiye yeni model fiyatı açıklandı")
        global_score, _ = evaluate_news_value("Toyota unveils new model")
        self.assertGreater(local, global_score)
        self.assertIn("Türkiye bağlantısı", reason)
        self.assertIn("Fiyat/vergi", reason)

    def test_turkish_case_and_dotted_letters(self):
        self.assertEqual(evaluate_news_value("TOGG TÜRKİYE YATIRIM FİYAT"), evaluate_news_value("Togg Türkiye yatırım fiyat"))

    def test_webinar_is_demoted_even_with_prominent_keywords(self):
        advert, reason = evaluate_news_value("Sponsored webinar: Toyota Turkey factory investment prices")
        news, _ = evaluate_news_value("Toyota factory investment")
        self.assertLess(advert, news)
        self.assertIn("webinar", reason)

    def test_article_footer_does_not_demote_real_news(self):
        a, _ = evaluate_news_value("Toyota announces factory investment", "Automotive news.")
        b, _ = evaluate_news_value("Toyota announces factory investment", "Automotive news. Register now for our webinar.")
        self.assertEqual(a, b)

    def test_unrelated_turkey_recipe_gets_no_turkey_boost(self):
        score, reason = evaluate_news_value("Turkey recipe for dinner")
        self.assertEqual(score, 0)
        self.assertNotIn("Türkiye bağlantısı", reason)

    def test_unknown_language_is_neutral_not_discarded(self):
        self.assertEqual(evaluate_news_value("Новая модель представлена")[0], 20)

    def test_scores_are_bounded_and_repetition_does_not_stack(self):
        title = "Toyota Türkiye fiyat yatırım yeni model recall"
        self.assertEqual(evaluate_news_value(title)[0], evaluate_news_value(title * 10)[0])
        self.assertLessEqual(evaluate_news_value(title)[0], 100)


if __name__ == "__main__":
    unittest.main()
