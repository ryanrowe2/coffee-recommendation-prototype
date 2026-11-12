"""Exercise both real server commands, signed delivery and persisted HTTP results."""

from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import hmac
from http.cookiejar import CookieJar
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

import pytest

from app.config import ROOT

pytest.importorskip("flask", reason="Flask required for runtime certification")
pytest.importorskip("waitress", reason="Waitress required for runtime certification")


@pytest.mark.parametrize("server_kind", ["flask", "waitress"])
def test_documented_servers_complete_http_workflow(tmp_path, server_kind, example_payload):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    secret = "synthetic-runtime-test-secret-123456"
    db = tmp_path / "runtime.sqlite3"
    env = {
        **os.environ,
        "APP_MODE": "local",
        "APP_DB_PATH": str(db),
        "PORT": str(port),
        "TYPEFORM_WEBHOOK_SECRET": secret,
        "TYPEFORM_FORM_ID": "DEMO_COFFEE_FORM",
        "APP_CATALOG_PATH": str(ROOT / "data/catalog.json"),
    }
    command = (
        [sys.executable, "-m", "app"]
        if server_kind == "waitress"
        else [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "app:create_app",
            "run",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
    )
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    origin = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))

    def request(path, data=None, headers=None):
        try:
            response = opener.open(Request(origin + path, data=data, headers=headers or {}), timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read(), response.url

    def webhook(payload, signature=None):
        raw = json.dumps(payload).encode()
        signed = (
            "sha256=" + base64.b64encode(hmac.new(secret.encode(), raw, hashlib.sha256).digest()).decode()
        )
        return request(
            "/typeform/webhook",
            raw,
            {"Content-Type": "application/json", "Typeform-Signature": signature or signed},
        )

    try:
        for _ in range(80):
            try:
                status, raw, _ = request("/health")
                assert status == 200 and json.loads(raw)["status"] == "ok"
                break
            except (URLError, OSError):
                assert process.poll() is None
                time.sleep(0.05)
        else:
            pytest.fail("Server did not start")
        status, raw, _ = request("/")
        assert status == 200
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', raw).group(1).decode()
        nonce = re.search(rb'name="form_nonce" value="([^"]+)"', raw).group(1).decode()
        form = urlencode({"csrf_token": csrf, "form_nonce": nonce, "roast_level": "light"}).encode()
        status, html, result_url = request(
            "/demo/submit", form, {"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert status == 200 and html.count(b'class="product-card"') == 3
        rid = urlsplit(result_url).path.rsplit("/", 1)[1]
        status, raw, _ = request("/api/recommendations/" + rid)
        record = json.loads(raw)
        assert status == 200 and record["preferences"]["roast_level"] == "light"
        with closing(sqlite3.connect(db)) as con:
            stored = con.execute(
                "SELECT recommendations_json FROM responses WHERE response_id=?", (rid,)
            ).fetchone()[0]
        assert record["recommendations"] == json.loads(stored)
        assert (
            request("/demo/submit", form, {"Content-Type": "application/x-www-form-urlencoded"})[2]
            == result_url
        )
        for duplicate in (False, True):
            status, raw, _ = webhook(example_payload)
            assert status == 200 and json.loads(raw)["duplicate"] is duplicate
        sender = subprocess.run(
            [sys.executable, "scripts/send_mock_webhook.py"],
            env={**env, "MOCK_WEBHOOK_URL": origin + "/typeform/webhook"},
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert sender.returncode == 0 and '"duplicate":true' in sender.stdout.replace(" ", "")
        assert webhook(example_payload, "sha256=invalid")[0] == 401
        assert webhook({"event_type": "wrong"})[0] == 422
        assert request("/typeform/webhook", b"{}", {"Content-Type": "application/json"})[0] == 401
        assert request("/typeform/webhook", b"x" * 70000, {"Content-Type": "application/json"})[0] == 413
        assert request("/demo/submit", b"roast_level=light")[0] == 403
        for path, expected in [
            ("/missing", 404),
            ("/api/recommendations/missing-record", 404),
            ("/api/recommendations/short", 400),
            ("/results/short", 404),
            ("/debug", 404),
        ]:
            status, raw, _ = request(path)
            assert status == expected
            assert b"Traceback" not in raw and str(db).encode() not in raw
    finally:
        process.send_signal(signal.SIGINT)
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=3)
            pytest.fail("Server failed clean shutdown: " + output)
        assert process.returncode == 0, output
        assert "Traceback" not in output, output
