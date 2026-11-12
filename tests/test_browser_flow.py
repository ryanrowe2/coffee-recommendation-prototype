"""Real Chromium journey from form through Flask routes to clipboard result URLs."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from threading import Thread

import pytest

from app import create_app

pytest.importorskip("flask", reason="Flask required for browser integration")
playwright = pytest.importorskip("playwright.sync_api", reason="Playwright required for browser integration")

from werkzeug.serving import make_server  # noqa: E402  (requires Flask/Werkzeug installed)


def test_real_chromium_form_result_api_and_clipboard(local_config):
    app = create_app(local_config)
    server = make_server("127.0.0.1", 0, app)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    address = f"http://127.0.0.1:{server.server_port}"
    try:
        with playwright.sync_playwright() as pw:
            bundled = Path(pw.chromium.executable_path)
            external = os.environ.get("COFFEE_BROWSER_PATH") or shutil.which("chromium")
            executable = str(bundled) if bundled.exists() else external
            if not executable:
                if os.environ.get("COFFEE_REQUIRE_BROWSER") == "1":
                    pytest.fail("Chromium missing; CI browser test must not silently skip")
                pytest.skip("Chromium executable unavailable")
            browser = pw.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox"])
            try:
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    permissions=["clipboard-read", "clipboard-write"],
                )
                errors = []
                console_errors = []
                context.on("weberror", lambda error: errors.append(str(error)))
                page = context.new_page()
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text) if message.type == "error" else None,
                )
                page.goto(address + "/", wait_until="networkidle")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.keyboard.press("Tab")
                assert page.evaluate("document.activeElement.tagName") == "A"
                assert page.locator("input:not([type=hidden]), select, textarea").evaluate_all(
                    "els => els.every(e => e.labels && e.labels.length > 0)"
                )
                if os.environ.get("COFFEE_CAPTURE_BROWSER") == "1":
                    Path(".ci_artifacts").mkdir(exist_ok=True)
                    page.screenshot(path=".ci_artifacts/entry-live-desktop.png", full_page=True)
                    page.locator(".coffee-form").screenshot(path=".ci_artifacts/form-live.png")
                page.locator("#brew_method").select_option("pour-over")
                page.locator('input[name="roast_level"][value="light"]').check()
                page.locator('input[name="flavor_notes"][value="citrus"]').check()
                page.locator("#caffeine_level").select_option("decaf")
                page.locator("#style_preference").select_option("bright")
                page.get_by_role("button", name="Find my three coffees").click()
                page.wait_for_url("**/results/*")
                assert page.locator(".product-card").count() == 3
                if os.environ.get("COFFEE_CAPTURE_BROWSER") == "1":
                    target = Path(".ci_artifacts")
                    target.mkdir(exist_ok=True)
                    page.screenshot(path=str(target / "results-live-desktop.png"), full_page=True)
                    page.locator(".result-grid").screenshot(path=str(target / "cards-live.png"))
                assert "Mistline Decaf" in page.content()
                assert "Sunbeam Citrus" not in page.locator(".result-grid").inner_text()
                assert (
                    page.locator(".product-card").first.locator(".score-value").inner_text().endswith("pts")
                )
                page.locator(".copy-btn").first.click()
                page.locator(".copy-btn").first.click()
                assert "Example URL copied" in page.locator(".copy-btn").first.inner_text()
                page.wait_for_timeout(2200)
                assert "Copy example cart URL" in page.locator(".copy-btn").first.inner_text()
                copied = page.evaluate("navigator.clipboard.readText()")
                assert copied.startswith("https://shop.example/cart/")
                assert "Copy example cart URL" in page.locator(".copy-btn").first.inner_text()
                record_url = page.locator(".api-link").get_attribute("href")
                response = page.request.get(address + record_url)
                assert response.status == 200
                body = response.json()
                assert body["preferences"]["caffeine_level"] == "decaf"
                assert body["catalog_digest"] == app.extensions["coffee_catalog_digest"]
                assert len(body["recommendations"]) == 3
                for index, product in enumerate(body["recommendations"]):
                    card = page.locator(".product-card").nth(index)
                    assert card.locator("h2").inner_text() == product["title"]
                    assert card.locator(".product-reason").inner_text() == product["why"]
                    assert card.locator(".score-value").inner_text() == f"{product['score']} pts"
                    assert product["score"] == sum(product["score_breakdown"].values())
                    assert product["rank"] == index + 1
                result_url = page.url
                page.reload(wait_until="networkidle")
                assert page.url == result_url
                assert (page.request.get(address + record_url)).json() == body
                api_page = context.new_page()
                assert api_page.goto(address + record_url).status == 200
                assert body["response_id"] in api_page.locator("body").inner_text()
                api_page.close()
                mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
                mobile.on(
                    "console",
                    lambda message: console_errors.append(message.text) if message.type == "error" else None,
                )
                mobile.goto(address + "/", wait_until="networkidle")
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
                if os.environ.get("COFFEE_CAPTURE_BROWSER") == "1":
                    mobile.screenshot(path=".ci_artifacts/entry-live-mobile.png", full_page=True)
                mobile.locator("#caffeine_level").select_option("decaf")
                mobile.get_by_role("button", name="Find my three coffees").click()
                mobile.wait_for_url("**/results/*")
                assert mobile.locator(".product-card").count() == 3
                assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                if os.environ.get("COFFEE_CAPTURE_BROWSER") == "1":
                    mobile.screenshot(
                        path=str(Path(".ci_artifacts") / "results-live-mobile.png"), full_page=True
                    )
                assert mobile.locator(".results-sidebar").inner_text().find("Decaf") >= 0
                assert not console_errors, console_errors
                assert mobile.goto(address + "/results/missing-record").status == 404
                mobile.goto(address + "/", wait_until="networkidle")
                mobile.get_by_role("button", name="Find my three coffees").click()
                assert mobile.locator(".form-error").is_visible()
                mobile.close()
                tab_one = context.new_page()
                tab_two = context.new_page()
                tab_one.goto(address + "/", wait_until="networkidle")
                tab_two.goto(address + "/", wait_until="networkidle")
                assert tab_one.get_by_role("group", name="Your go-to roast?").count() == 1
                assert tab_two.get_by_role("group", name="How do you take it?").count() == 1
                assert (
                    tab_one.locator('input[name="csrf_token"]').input_value()
                    == tab_two.locator('input[name="csrf_token"]').input_value()
                )
                assert (
                    tab_one.locator('input[name="form_nonce"]').input_value()
                    != tab_two.locator('input[name="form_nonce"]').input_value()
                )
                tab_one.locator('input[name="roast_level"][value="light"]').check()
                tab_two.locator('input[name="roast_level"][value="dark"]').check()
                tab_one.get_by_role("button", name="Find my three coffees").click()
                tab_one.wait_for_url("**/results/*")
                tab_two.get_by_role("button", name="Find my three coffees").click()
                tab_two.wait_for_url("**/results/*")
                assert tab_one.url != tab_two.url
                tab_one.close()
                tab_two.close()
                assert not errors, errors
                context.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        worker.join(timeout=4)
        server.server_close()
