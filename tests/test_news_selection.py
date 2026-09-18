import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.database import crud
from app.models.news import News
from app.services.news_selection import content_skip_reason, title_key, select_for_ai


BODY = ("The manufacturer announced a new electric vehicle for the European market. "
        "Production will begin at its existing factory next year with additional workers. "
        "The company described battery capacity, charging equipment and dealer training plans. "
        "Prices and delivery dates will be confirmed separately for each country before orders open.")
TITLE = "Toyota announces new electric vehicle production plans for Europe"


class NewsSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'selection.db'}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)
        self.patcher = patch.object(crud, "SessionLocal", self.Session)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def article(self, number, **values):
        return dict(title=TITLE, content=BODY, source="Publisher",
                    link=f"https://example.test/{number}") | values

    def test_group_retains_both_sources_and_import_is_idempotent(self):
        batch = [self.article(1), self.article(2, title=TITLE + " - Reuters", source="Reuters Otomotiv (Google Haberler)")]
        rows = crud.save_news(batch)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1].duplicate_of_id, rows[0].id)
        self.assertEqual(rows[1].status, "ai_skipped")
        self.assertEqual(len(crud.save_news(batch)), 0)
        overview = crud.get_news()
        self.assertEqual(overview["total"], 1)
        self.assertEqual(len(overview["items"][0].related_sources), 1)
        self.assertEqual(crud.get_news(status="ai_skipped")["total"], 1)

    def test_same_batch_link_duplicate_is_not_inserted_twice(self):
        self.assertEqual(len(crud.save_news([self.article(1), self.article(1)])), 1)

    def test_numbers_and_negation_are_not_merged(self):
        rows = crud.save_news([
            self.article(1, title=TITLE + " in 2026"),
            self.article(2, title=TITLE + " in 2027"),
            self.article(3, title=TITLE.replace("announces", "does not announce")),
        ])
        self.assertTrue(all(row.duplicate_of_id is None for row in rows))

    def test_short_first_article_does_not_suppress_full_text(self):
        rows = crud.save_news([self.article(1, content=TITLE), self.article(2)])
        self.assertEqual(rows[0].status, "ai_skipped")
        self.assertEqual(rows[1].status, "new")
        self.assertIsNone(rows[1].duplicate_of_id)

    def test_deleted_parent_does_not_hide_alternative(self):
        rows = crud.save_news([self.article(1), self.article(2)])
        with self.Session() as db:
            db.get(News, rows[0].id).status = "deleted"
            db.commit()
        self.assertEqual(crud.get_news()["total"], 1)

    def test_title_repetition_and_html_do_not_pass_quality_gate(self):
        self.assertIsNotNone(content_skip_reason(News(title=TITLE, content=(TITLE + " ") * 20)))
        self.assertIsNotNone(content_skip_reason(News(title=TITLE, content="<script>" + BODY + "</script>")))
        self.assertIsNone(content_skip_reason(News(title=TITLE, content="<p>" + BODY + "</p>")))

    def test_manual_rejection_preserves_editor_work(self):
        from app.ai import worker
        rows = crud.save_news([self.article(1, content=TITLE)])
        with self.Session() as db:
            row = db.get(News, rows[0].id)
            row.summary = "Editörün özeti"
            row.status = "editor_review"
            db.commit()
        with patch.object(worker, "SessionLocal", self.Session), patch.object(worker, "process") as model:
            with self.assertRaises(ValueError):
                worker.process_ai_news(rows[0].id)
            model.assert_not_called()
        with self.Session() as db:
            self.assertEqual(db.get(News, rows[0].id).summary, "Editörün özeti")
            self.assertEqual(db.get(News, rows[0].id).status, "editor_review")

    def test_only_known_publisher_suffix_is_removed(self):
        self.assertEqual(title_key(TITLE + " - Reuters", "Reuters Otomotiv (Google Haberler)"), title_key(TITLE))
        self.assertNotEqual(title_key(TITLE + " - delayed"), title_key(TITLE))

    def test_old_story_does_not_suppress_new_story(self):
        rows = crud.save_news([self.article(1)])
        with self.Session() as db:
            db.get(News, rows[0].id).created_at = datetime.now(UTC) - timedelta(hours=49)
            db.commit()
        self.assertIsNone(crud.save_news([self.article(2)])[0].duplicate_of_id)

    def test_worker_skips_short_backlog_without_model_call(self):
        from app.services import ai_worker
        with self.Session() as db:
            db.add(News(**self.article(1, content=TITLE), status="new"))
            db.commit()
        with patch.object(ai_worker, "SessionLocal", self.Session), patch.object(
            ai_worker, "refresh_ai_queue"
        ), patch.object(ai_worker, "process") as model:
            ai_worker.process_ai_news()
            model.assert_not_called()
        with self.Session() as db:
            row = db.query(News).one()
            self.assertEqual(row.status, "ai_skipped")
            self.assertEqual(row.ai_attempts, 0)
            self.assertIn("Yeterli kaynak metni", row.ai_last_error)

    def test_group_links_and_reason_render_in_editor_table(self):
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        rows = crud.save_news([self.article(1), self.article(2)])
        env = Environment(loader=FileSystemLoader("app/templates"), autoescape=select_autoescape())
        template = env.get_template("partials/news_table.html")
        html = template.render(news_list=crud.get_news()["items"])
        self.assertIn("1 ek kaynak", html)
        self.assertIn(f'/editor/{rows[1].id}', html)
        skipped = template.render(news_list=crud.get_news(status="ai_skipped")["items"])
        self.assertIn("tekrar AI işlemi yapılmadı", skipped)

    def test_upgrade_is_repeatable_and_preserves_existing_data(self):
        from sqlalchemy import text, inspect
        from app.database import schema
        legacy = create_engine("sqlite://")
        try:
            with legacy.begin() as connection:
                connection.execute(text("CREATE TABLE news (id INTEGER PRIMARY KEY, title TEXT, published BOOLEAN, status TEXT, ai_processed BOOLEAN, created_at DATETIME)"))
                connection.execute(text("INSERT INTO news (id,title,status,published) VALUES (1,'Saved article','new',0)"))
            with patch.object(schema, "engine", legacy):
                schema.ensure_database_upgrades()
                schema.ensure_database_upgrades()
            self.assertIn("duplicate_of_id", {c["name"] for c in inspect(legacy).get_columns("news")})
            with legacy.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT title FROM news WHERE id=1")).scalar(), "Saved article")
        finally:
            legacy.dispose()

    def test_failed_parent_does_not_hide_or_block_requeued_alternative(self):
        rows = crud.save_news([self.article(1), self.article(2)])
        with self.Session() as db:
            db.get(News, rows[0].id).status = "ai_failed"
            alternative = db.get(News, rows[1].id)
            alternative.status = "ai_pending"
            db.commit()
        self.assertEqual(crud.get_news()["total"], 2)
        with self.Session() as db:
            alternative = db.get(News, rows[1].id)
            self.assertTrue(select_for_ai(db, alternative))
            self.assertIsNone(alternative.duplicate_of_id)
            self.assertFalse(alternative.is_duplicate)
            self.assertIsNone(alternative.ai_last_error)

    def test_stale_parent_does_not_suppress_new_import(self):
        rows = crud.save_news([self.article(1)])
        with self.Session() as db:
            db.get(News, rows[0].id).status = "ai_skipped"
            db.commit()
        self.assertIsNone(crud.save_news([self.article(2)])[0].duplicate_of_id)

    def test_detail_contains_related_sources_and_no_deleted_parent_link(self):
        rows = crud.save_news([self.article(1), self.article(2)])
        self.assertEqual(len(crud.get_news_by_id(rows[0].id).related_sources), 1)
        self.assertEqual(crud.get_news_by_id(rows[1].id).group_parent.id, rows[0].id)
        with self.Session() as db:
            db.get(News, rows[0].id).status = "deleted"
            db.commit()
        self.assertIsNone(crud.get_news_by_id(rows[1].id).group_parent)

    def test_detail_explanation_escapes_untrusted_text(self):
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        env = Environment(loader=FileSystemLoader("app/templates"), autoescape=select_autoescape())
        row = News(title=TITLE, status="ai_skipped", ai_last_error='<script>alert(1)</script>')
        html = env.get_template("partials/news_selection_info.html").render(news=row)
        self.assertIn("Bu haber neden otomatik işlenmedi?", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_instagram_fact_warning_is_persisted_in_review(self):
        row = crud.save_news([self.article(1)])[0]
        saved = crud.update_instagram_content(
            row.id, "Başlık", "Açıklama", "#otomobil", "Görsel",
            fact_check_notes="Fiyat–para birimi eşleşmesi doğrulanamadı",
        )
        self.assertEqual(saved.status, "editor_review")
        self.assertEqual(saved.instagram_caption, "Açıklama")
        self.assertIn("para birimi", crud.get_news_by_id(row.id).fact_check_notes)

    def test_value_ranking_is_persistent_and_keeps_low_score_items(self):
        rows = crud.save_news([
            self.article(1, title="Toyota Türkiye yeni model fiyatı açıklandı"),
            self.article(2, title="Sponsored webinar: electric vehicle prices"),
        ])
        result = crud.get_news(sort="news_value")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["items"][0].id, rows[0].id)
        self.assertLess(rows[1].news_value, rows[0].news_value)
        self.assertIn("Türkiye bağlantısı", crud.get_news_by_id(rows[0].id).news_value_reason)

    def test_backfill_does_not_change_editor_work_or_ai_score(self):
        from app.services.news_value import score_recent_unrated
        with self.Session() as db:
            row = News(**self.article(1), summary="Editör özeti", importance=8, status="editor_review")
            db.add(row)
            db.commit()
            self.assertEqual(score_recent_unrated(db), 1)
            db.commit()
            self.assertEqual(score_recent_unrated(db), 0)
            self.assertEqual(row.summary, "Editör özeti")
            self.assertEqual(row.importance, 8)
            self.assertEqual(row.status, "editor_review")


if __name__ == "__main__":
    unittest.main()
