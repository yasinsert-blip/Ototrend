"""Geçici verilerle tarayıcı kontrolü: python -X utf8 scripts/verify_editor_ui.py."""

from pathlib import Path
from datetime import UTC, datetime
import sys
import socket
import threading
import time

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from playwright.sync_api import sync_playwright, expect
from test_editor_and_source_workflows import EditorAndSourceWorkflowTests
from test_news_selection import BODY
from app.models.news import News


def main():
    fixture = EditorAndSourceWorkflowTests()
    fixture.setUp()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(fixture.client.app, log_level="error"))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    worker.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        assert server.started, "Test server did not start"
        fixture.add_news()
        with fixture.Session() as db:
            db.get(News, 1).title = "Audi Q3 electric SUV production starts in Europe"
            db.get(News, 1).content = BODY
            db.get(News, 1).ai_processed = True
            db.get(News, 1).telegram_sent = True
            db.get(News, 1).ai_run_started_at = datetime.now(UTC)
            db.get(News, 1).ai_run_finished_at = datetime.now(UTC)
            db.get(News, 1).ai_run_seconds = 84
            db.get(News, 1).ai_model_seconds = 80
            db.get(News, 1).ai_input_chars = 800
            db.get(News, 2).title = "Production of Audi Q3 electric SUV starts in Europe"
            db.commit()
        fixture.add_source()
        fixture.add_source(name="Kontrol gereken kaynak", scraper="RSS", rss_url="", enabled=False)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.context.add_cookies([{
                    "name": "session", "value": fixture.client.cookies.get("session"),
                    "url": base_url,
                }])
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("requestfailed", lambda request: print(f"Request failed: {request.url}: {request.failure}"))
                page.goto(base_url + "/editor", wait_until="networkidle")
                assert page.locator("#news-status").is_visible()
                page.locator("#news-search").fill("şarj")
                page.locator("#news-brand").select_option("Ford")
                page.locator("#news-status").select_option("ai_ready")
                page.locator("#news-sort").select_option("oldest")
                page.get_by_role("button", name="Filtrele", exact=True).click()
                page.wait_for_load_state("networkidle")
                page.get_by_role("link", name="Sonraki", exact=True).first.click()
                page.wait_for_load_state("networkidle")
                assert "page=2" in page.url
                assert page.locator("#news-search").input_value() == "şarj"
                assert page.locator("#news-status").input_value() == "ai_ready"

                output = ROOT / "logs" / "ui-verification"
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / "editor-desktop.png"), full_page=True)
                page.goto(base_url + "/editor?section=review", wait_until="networkidle")
                expect(page.get_by_role("link", name="İnceleme bekleyenler", exact=True)).to_have_attribute("aria-current", "page")
                page.goto(base_url + "/editor/1", wait_until="networkidle")
                expect(page.get_by_label("İşlem durumu")).to_contain_text("AI tamamlandı")
                expect(page.get_by_label("İşlem durumu")).to_contain_text("Telegram gönderildi")
                page.get_by_text("Son AI işleminin ölçümleri", exact=True).click()
                expect(page.get_by_text("İşlem: 84 saniye", exact=True)).to_be_visible()
                expect(page.get_by_text("Girdi: 800 karakter", exact=True)).to_be_visible()
                source_box = page.locator(".source-panel").bounding_box()
                draft_box = page.locator(".draft-panel").bounding_box()
                assert source_box["x"] < draft_box["x"]
                page.screenshot(path=str(output / "comparison-desktop.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.locator(".source-panel").bounding_box()["y"] < page.locator(".draft-panel").bounding_box()["y"]
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                expect(page.get_by_text("İşlem: 84 saniye", exact=True)).to_be_visible()
                page.screenshot(path=str(output / "comparison-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1000})
                page.goto(base_url + "/editor/2", wait_until="networkidle")
                page.get_by_text("Benzer haber önerileri (1)", exact=True).click()
                page.screenshot(path=str(output / "similar-news-desktop.png"), full_page=True)
                proposal = page.locator('form[action="/editor/2/group"]')
                proposal.locator('input[name="confirmed"]').check()
                proposal.get_by_role("button").click()
                page.wait_for_load_state("networkidle")
                expect(page.get_by_role("button", name="Gruptan ayır", exact=True)).to_be_visible()
                page.get_by_role("button", name="Gruptan ayır", exact=True).click()
                page.wait_for_load_state("networkidle")
                expect(page.get_by_text("Benzer haber önerileri (1)", exact=True)).to_be_visible()
                page.goto(base_url + "/sources", wait_until="networkidle")
                page.locator("#source-state").select_option("attention")
                page.get_by_role("button", name="Filtrele", exact=True).click()
                page.wait_for_load_state("networkidle")
                assert page.get_by_text("Kontrol gereken kaynak", exact=True).is_visible()
                assert page.get_by_role("button", name="Etkinleştir", exact=True).is_disabled()
                page.screenshot(path=str(output / "sources-desktop.png"), full_page=True)

                page.goto(base_url + "/sources/new", wait_until="networkidle")
                assert page.locator("#source-rss").evaluate("(input) => input.required")
                page.locator("#source-reader").select_option("LOG")
                assert not page.locator("#source-rss").evaluate("(input) => input.required")
                page.locator("#source-name").fill("Yeni özel kaynak")
                page.get_by_role("button", name="Kaydet", exact=True).click()
                page.wait_for_url(base_url + "/sources")
                expect(page.get_by_text("Kaynak eklendi.", exact=True)).to_be_visible()

                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(base_url + "/editor", wait_until="networkidle")
                assert page.locator("#news-search").is_visible()
                page.screenshot(path=str(output / "editor-mobile.png"))
                overflow = page.evaluate("""() => [...document.querySelectorAll('body *')]
                    .filter(el => el.getBoundingClientRect().right > innerWidth + 1 && !el.closest('.table-responsive'))
                    .map(el => ({tag: el.tagName, class: el.className, right: el.getBoundingClientRect().right}))""")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), overflow
                assert not errors, errors
                print("Browser checks passed: filters, pagination, source validation, creation, mobile.")
                print(f"Screenshots: {output}")
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(timeout=5)
        listener.close()
        fixture.tearDown()


if __name__ == "__main__":
    main()
