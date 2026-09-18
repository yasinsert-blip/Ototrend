import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.compare_local_models import aggregate, freeze_samples, inspect_output


class ModelComparisonTests(unittest.TestCase):
    def sample(self, **changes):
        value = dict(title_tr="Audi yeni otomobilini tanıttı", summary_tr="Audi, yeni elektrikli otomobilini Paris'te tanıttı.",
                     brand="Audi", model="A2", category="EV", importance=7)
        value.update(changes)
        return json.dumps(value, ensure_ascii=False)

    def test_valid_result(self):
        result = inspect_output(self.sample())
        self.assertTrue(result["schema_ok"])
        self.assertTrue(result["language_ok"])

    def test_non_object_and_malformed_json(self):
        self.assertFalse(inspect_output("[]")["schema_ok"])
        self.assertFalse(inspect_output("```json\n{}\n```")["json_ok"])
        self.assertFalse(inspect_output('{"title_tr":')["json_ok"])

    def test_schema_failure_does_not_crash(self):
        for change in (dict(category=[]), dict(importance=True), dict(importance=11), dict(brand=7), dict(extra="x")):
            with self.subTest(change=change):
                self.assertFalse(inspect_output(self.sample(**change))["schema_ok"])

    def test_language_check_is_separate_from_schema(self):
        value = inspect_output(self.sample(title_tr="The new car is here", summary_tr="The new vehicle is ready for the world."))
        self.assertTrue(value["schema_ok"])
        self.assertFalse(value["language_ok"])

    def test_aggregate_counts_failures_in_time(self):
        rows = [dict(wall_seconds=10, json_ok=True, schema_ok=True, language_ok=True),
                dict(wall_seconds=30, json_ok=False, schema_ok=False, language_ok=False)]
        result = aggregate(rows)
        self.assertEqual(result["seconds_per_accepted"], 40)
        self.assertEqual(result["median_seconds"], 20)

    def test_source_balanced_sample_excludes_deleted_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "news.db"
            with closing(sqlite3.connect(database)) as db:
                db.execute("CREATE TABLE news (id INTEGER, title TEXT, content TEXT, source TEXT, link TEXT, status TEXT)")
                for i, source, status in [(1, "A", "new"), (2, "A", "new"), (3, "B", "new"), (4, "A", "deleted")]:
                    db.execute("INSERT INTO news VALUES (?,?,?,?,?,?)", (i, f"Title {i}", f"Article {i} " + "source text " * 20, source, "https://example.test", status))
                db.commit()
            before = database.read_bytes()
            samples = freeze_samples(database, 2)
            self.assertEqual({row["source"] for row in samples}, {"A", "B"})
            self.assertNotIn(4, [row["id"] for row in samples])
            self.assertEqual(database.read_bytes(), before)
            with self.assertRaises(RuntimeError):
                freeze_samples(database, 5)


if __name__ == "__main__":
    unittest.main()
