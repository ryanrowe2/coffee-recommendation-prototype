"""Real loopback WSGI request smoke test (runs with Flask installed in CI).

This deliberately uses the standard-library WSGI server and HTTP client rather
than Flask's in-process test client, exercising cookies and redirects over HTTP.
"""

from __future__ import annotations

from http.cookiejar import CookieJar
import json
import re
from threading import Thread
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request

from scripts.loopback_http import loopback_opener
from wsgiref.simple_server import make_server

import pytest

from app import create_app

pytest.importorskip("flask", reason="Flask must be installed for HTTP integration")


def test_actual_loopback_http_flow(local_config):
    app = create_app(local_config)
    app.testing = True
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    opener = loopback_opener(HTTPCookieProcessor(CookieJar()))
    try:
        with opener.open(origin + "/health", timeout=5) as response:
            assert response.status == 200
            assert json.load(response)["status"] == "ok"
        with opener.open(origin + "/", timeout=5) as response:
            page = response.read()
            assert response.headers["Cache-Control"] == "no-store"
        token = re.search(rb'name="csrf_token" value="([^"]+)"', page).group(1).decode()
        nonce = re.search(rb'name="form_nonce" value="([^"]+)"', page).group(1).decode()
        body = urlencode(
            {"csrf_token": token, "form_nonce": nonce, "roast_level": "light", "brew_method": "pour-over"}
        ).encode()
        with opener.open(
            Request(
                origin + "/demo/submit",
                body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ),
            timeout=5,
        ) as response:
            html = response.read()
            result_path = urlsplit(response.url).path
            assert result_path.startswith("/results/")
            assert html.count(b'class="product-card"') == 3
        rid = result_path.removeprefix("/results/")
        with opener.open(origin + "/api/recommendations/" + rid, timeout=5) as response:
            result = json.load(response)
            assert len(result["recommendations"]) == 3
            assert result["preferences"]["roast_level"] == "light"
            assert all(
                item["cart_preview_url"].startswith("https://shop.example/")
                for item in result["recommendations"]
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
