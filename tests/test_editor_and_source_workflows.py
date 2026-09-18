"""Gerçek ekran isteklerini geçici veritabanında doğrular; dış servislere bağlanmaz."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.database import crud, source_crud
from app.database.database import Base
from app.models.news import News
from app.models.source import Source
from app.services import source_service
from app.views import news as news_view, sources as source_view


class EditorAndSourceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.directory.name) / 'workflows.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.patches = [
            patch.object(module, "SessionLocal", self.Session)
            for module in (crud, source_crud, source_service, news_view)
        ]
        for replacement in self.patches:
            replacement.start()
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-only-key")
        app.mount("/static", StaticFiles(directory="app/static"), name="static")
        app.include_router(news_view.router)
        app.include_router(source_view.router)

        @app.post("/test-login")
        def login(request: Request):
            request.session["authenticated"] = True
            return {"ok": True}

        self.client = TestClient(app)
        self.client.post("/test-login")
        self.now = datetime.now(UTC)

    def tearDown(self):
        self.client.close()
        for replacement in reversed(self.patches):
            replacement.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def add_news(self, count=125):
        with self.Session() as db:
            db.add_all([
                News(
                    id=index, title=f"Original {index}",
                    translated_title=f"Ford haber {index}",
                    summary="Yeni şarj istasyonları açıklandı.",
                    brand="Ford", category="Charging", status="ai_ready",
                    importance=8, link=f"https://example.test/news/{index}",
                    created_at=self.now, updated_at=self.now,
                )
                for index in range(1, count + 1)
            ])
            db.commit()

    def add_source(self, **overrides):
        values = dict(
            name="Ford newsroom", scraper="RSS",
            rss_url="https://example.test/feed", website="https://example.test",
            priority=2, enabled=True, is_oem=True, brand="Ford", source_type="oem",
        )
        values.update(overrides)
        with self.Session() as db:
            source = Source(**values)
            db.add(source)
            db.commit()
            return source.id

    def test_combined_filters_search_summary_and_respect_deleted_records(self):
        self.add_news(6)
        with self.Session() as db:
            db.get(News, 2).brand = "BMW"
            db.get(News, 3).status = "deleted"
            db.get(News, 4).category = "Other"
            db.get(News, 5).importance = 3
            db.commit()
        response = self.client.get("/editor", params=dict(
            keyword="şarj", brand="Ford", category="Charging",
            status="ai_ready", min_importance=8,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row.id for row in response.context["news_list"]], [6, 1])
        self.assertEqual(response.context["pagination"]["total"], 2)
        html = BeautifulSoup(response.text, "html.parser")
        self.assertEqual(html.select_one("#news-status option[selected]")["value"], "ai_ready")

    def test_pagination_reaches_older_news_and_keeps_filters(self):
        self.add_news()
        params = dict(keyword="şarj", brand="Ford", status="ai_ready",
                      page=3, page_size=50, sort="oldest", min_importance=8)
        response = self.client.get("/editor", params=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["news_list"]), 25)
        self.assertEqual(response.context["news_list"][0].id, 101)
        previous = response.context["pagination"]["previous"]
        query = parse_qs(urlsplit(previous).query)
        for key in ("keyword", "brand", "status", "page_size", "sort", "min_importance"):
            self.assertEqual(query[key], [str(params[key])])
        self.assertEqual(query["page"], ["2"])
        self.assertEqual(self.client.get(previous).context["news_list"][0].id, 51)

    def test_importance_sort_and_literal_search(self):
        self.add_news(3)
        with self.Session() as db:
            db.get(News, 1).importance = 10
            db.get(News, 1).summary = "Yüzde 50% artış"
            db.commit()
        response = self.client.get("/editor?sort=importance")
        self.assertEqual([row.id for row in response.context["news_list"]], [1, 3, 2])
        self.assertEqual([row.id for row in crud.get_news(keyword="%")["items"]], [1])

    def test_news_value_sort_renders_and_retains_pagination(self):
        self.add_news(3)
        with self.Session() as db:
            db.get(News, 1).news_value = 80
            db.get(News, 1).news_value_reason = "Türkiye bağlantısı +25"
            db.get(News, 2).news_value = 0
            db.get(News, 3).news_value = 35
            db.commit()
        response = self.client.get("/editor?sort=news_value&page_size=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["news_list"][0].id, 1)
        self.assertIn("Haber değeri: 80/100", response.text)
        self.assertIn("Türkiye bağlantısı +25", response.text)
        next_page = response.context["pagination"]["next"]
        self.assertIn("sort=news_value", next_page)
        self.assertEqual(self.client.get(next_page).context["news_list"][0].id, 3)

    def test_workspaces_separate_review_and_ready(self):
        self.add_news(5)
        with self.Session() as db:
            db.get(News, 1).status = "instagram_ready"
            db.get(News, 2).status = "scheduled"
            db.get(News, 2).fact_check_notes = "Fiyat farklı"
            db.get(News, 3).status = "ai_failed"
            db.get(News, 4).status = "published"
            db.get(News, 5).news_value = 85
            db.commit()
        ids = lambda section: [row.id for row in self.client.get('/editor?section=' + section).context['news_list']]
        self.assertEqual(ids('ready'), [1])
        self.assertEqual(ids('review'), [5, 3, 2])
        self.assertEqual(ids('important'), [5])
        response = self.client.get('/editor?section=review&page_size=1')
        self.assertIn('section=review', response.context['pagination']['next'])
        self.assertIn('name="section" value="review"', response.text)

    def test_comparison_preserves_source_and_saves_draft(self):
        self.add_news(1)
        with self.Session() as db:
            db.get(News, 1).content = '<p>Original source text.</p><script>alert(1)</script>'
            db.commit()
        response = self.client.get('/editor/1')
        self.assertEqual(response.status_code, 200)
        html = BeautifulSoup(response.text, 'html.parser')
        self.assertIn('Original source text.', html.select_one('.source-copy').text)
        self.assertNotIn('alert(1)', html.select_one('.source-copy').text)
        self.assertIsNotNone(html.select_one('.draft-panel textarea[name=summary]'))
        saved = self.client.post('/editor/1', data=dict(translated_title='Düzenlenen başlık', summary='Editör özeti', category='EV', brand='Ford', importance=8, editor_note='Kontrol edildi'))
        self.assertEqual(saved.status_code, 200)
        with self.Session() as db:
            row = db.get(News, 1)
            self.assertEqual(row.summary, 'Editör özeti')
            self.assertEqual(row.content, '<p>Original source text.</p><script>alert(1)</script>')
            self.assertFalse(row.published)

    def test_similar_suggestion_requires_confirmation_and_can_be_undone(self):
        from app.services.similar_news import suggest_similar
        self.add_news(2)
        with self.Session() as db:
            first, second = db.get(News, 1), db.get(News, 2)
            first.title = "Audi Q3 electric SUV production starts in Europe"
            second.title = "Production of Audi Q3 electric SUV starts in Europe"
            first.content = ("The manufacturer announced a new electric vehicle for the European market. "
                             "Production will begin at its existing factory next year with additional workers. "
                             "The company described battery capacity, charging equipment and dealer training plans. "
                             "Prices and delivery dates will be confirmed separately for each country before orders open.")
            db.commit()
            self.assertEqual(suggest_similar(db, second)[0]['news'].id, 1)
        response = self.client.get('/editor/2')
        self.assertIn('Benzer haber önerileri', response.text)
        with self.Session() as db:
            self.assertIsNone(db.get(News, 2).duplicate_of_id)
        self.assertEqual(self.client.post('/editor/2/group', data={'parent_id': 1}).status_code, 422)
        response = self.client.post('/editor/2/group', data={'parent_id': 1, 'confirmed': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Gruptan ayır', response.text)
        with self.Session() as db:
            row = db.get(News, 2)
            self.assertEqual(row.duplicate_of_id, 1)
            self.assertEqual(row.summary, 'Yeni şarj istasyonları açıklandı.')
            self.assertEqual(row.status, 'ai_ready')
        self.assertEqual(self.client.post('/editor/2/ungroup').status_code, 200)
        with self.Session() as db:
            self.assertIsNone(db.get(News, 2).duplicate_of_id)
            db.get(News, 2).title = "Production of Audi Q5 electric SUV starts in Europe"
            db.commit()
        self.assertIn('Başlıklardaki sayılar farklı', self.client.get('/editor/2').text)
        with self.Session() as db:
            db.get(News, 2).status = "scheduled"
            db.commit()
        self.assertEqual(self.client.post('/editor/2/group', data={'parent_id': 1, 'confirmed': 'true'}).status_code, 409)

    def test_grouping_rejects_self_cycles_and_unauthenticated_requests(self):
        self.add_news(2)
        for child, parent in ((1, 1), (1, 2)):
            response = self.client.post(f'/editor/{child}/group', data={'parent_id': parent, 'confirmed': 'true'})
            self.assertEqual(response.status_code, 409)
        self.client.cookies.clear()
        self.assertEqual(self.client.post('/editor/2/group', data={'parent_id': 1, 'confirmed': 'true'}).status_code, 401)
        self.assertEqual(self.client.post('/editor/2/ungroup').status_code, 401)

    def test_forms_preserve_reader_and_oem_metadata(self):
        source_id = self.add_source(scraper="LOG", rss_url="")
        response = self.client.get(f"/sources/{source_id}/edit")
        html = BeautifulSoup(response.text, "html.parser")
        self.assertEqual(html.select_one("#source-reader option[selected]")["value"], "LOG")
        self.assertFalse(html.select_one("#source-rss").has_attr("required"))
        saved = self.client.post(f"/sources/{source_id}/edit", data=dict(
            name="Ford newsroom revised", scraper="LOG", rss_url="",
            website="https://example.test", priority=4, enabled="on",
        ))
        self.assertEqual(saved.status_code, 200)
        with self.Session() as db:
            source = db.get(Source, source_id)
            self.assertEqual((source.scraper, source.priority), ("LOG", 4))
            self.assertEqual((source.source_type, source.brand, source.is_oem), ("oem", "Ford", True))

    def test_invalid_rss_retains_form_values_without_saving(self):
        response = self.client.post("/sources/new", data=dict(
            name="Yeni kaynak", scraper="RSS", rss_url="", priority=3, enabled="on",
        ))
        self.assertEqual(response.status_code, 422)
        html = BeautifulSoup(response.text, "html.parser")
        self.assertEqual(html.select_one("#source-name")["value"], "Yeni kaynak")
        self.assertIn("RSS adresi gerekli", response.text)
        with self.Session() as db:
            self.assertEqual(db.query(Source).count(), 0)

    def test_create_and_duplicate_name_conflict(self):
        data = dict(name="Yeni RSS", scraper="RSS", rss_url="https://example.test/feed",
                    priority=4, enabled="on")
        self.assertEqual(self.client.post("/sources/new", data=data).status_code, 200)
        self.assertEqual(self.client.post("/sources/new", data=data).status_code, 422)
        with self.Session() as db:
            self.assertEqual(db.query(Source).count(), 1)
            self.assertEqual(db.query(Source).one().priority, 4)

    def test_pause_and_resume_keeps_history_and_filters(self):
        source_id = self.add_source(total_news=19)
        result = self.client.post(f"/sources/{source_id}/disable?q=Ford&state=inactive")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context["q"], "Ford")
        self.assertEqual(len(result.context["sources"]), 1)
        self.assertEqual(source_service.get_enabled_sources(), [])
        self.client.post(f"/sources/{source_id}/enable")
        with self.Session() as db:
            source = db.get(Source, source_id)
            self.assertTrue(source.enabled)
            self.assertEqual(source.total_news, 19)

    def test_attention_filter_and_unsafe_activation_are_explicit(self):
        valid_id = self.add_source()
        broken_id = self.add_source(name="Bozuk kaynak", scraper="RSS", rss_url="", enabled=False)
        response = self.client.get("/sources?state=attention")
        self.assertEqual([s.id for s in response.context["sources"]], [broken_id])
        self.assertEqual(response.context["health"]["active"], 1)
        self.assertEqual(response.context["health"]["needs_attention"], 1)
        self.client.post(f"/sources/{broken_id}/enable")
        with self.Session() as db:
            self.assertFalse(db.get(Source, broken_id).enabled)
            self.assertTrue(db.get(Source, valid_id).enabled)

    def test_pause_requires_authentication(self):
        source_id = self.add_source()
        self.client.cookies.clear()
        response = self.client.post(f"/sources/{source_id}/disable", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login")
        with self.Session() as db:
            self.assertTrue(db.get(Source, source_id).enabled)


if __name__ == "__main__":
    unittest.main()
