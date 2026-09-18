import unittest
from types import SimpleNamespace
from app.services.similar_news import headline_similarity


def article(title, translated=None):
    return SimpleNamespace(title=title, translated_title=translated, source="Test")


class SimilarNewsTests(unittest.TestCase):
    def test_reordered_words_are_suggested(self):
        self.assertGreaterEqual(headline_similarity(
            article("Audi Q3 electric SUV production starts in Europe"),
            article("Production of Audi Q3 electric SUV starts in Europe")), .55)

    def test_available_translation_can_bridge_languages(self):
        self.assertGreaterEqual(headline_similarity(
            article("Audi starts electric SUV production in Europe", "Audi elektrikli SUV üretimi Avrupa tesisinde başlıyor"),
            article("Avrupa tesisinde Audi elektrikli SUV üretimi başlıyor")), .55)

    def test_generic_brand_match_is_insufficient(self):
        self.assertEqual(headline_similarity(article("Ford unveils new car"), article("Ford announces new factory")), 0)

    def test_empty_titles_are_safe(self):
        self.assertEqual(headline_similarity(article(None), article("Audi Q3 arrives")), 0)
