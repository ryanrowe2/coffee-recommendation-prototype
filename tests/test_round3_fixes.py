"""Reproductions and permanent regression checks for independent audit round two."""

from __future__ import annotations

from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import sqlite3
import subprocess
import threading

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import ROOT
from app.preferences import normalize_preferences
from app.recommendations import rank_recommendations
from app.security import validate_origin
from app.storage import ResponseStore
from scripts import send_mock_webhook


@pytest.mark.parametrize("url", ["https://shop.example?", "https://shop.example#", "https://shop.example?#"])
def test_cors_origin_rejects_empty_query_fragment_delimiters(url):
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        validate_origin(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:5050/typeform/webhook?",
        "http://127.0.0.1:5050/typeform/webhook#",
    ],
)
def test_mock_url_rejects_empty_query_fragment_delimiters(url):
    with pytest.raises(ValueError):
        send_mock_webhook.validate_mock_url(url)


def test_foreign_keys_on_for_every_app_connection(tmp_path, catalog):
    store = ResponseStore(tmp_path / "data.db")
    store.initialize()
    prefs = normalize_preferences({"roast_level": "light"})
    store.save_once("a-valid-response-001", prefs, rank_recommendations(prefs, catalog))
    for _ in range(3):
        with store._connection() as con:
            assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                con.execute(
                    "INSERT INTO demo_submissions (nonce_hash, fingerprint, response_id) "
                    "VALUES ('orphaned-nonce', 'fingerprint', 'nonexistent-response')"
                )
            assert con.execute("SELECT COUNT(*) FROM demo_submissions").fetchone()[0] == 0


def test_initialize_rejects_legacy_orphan_records(tmp_path):
    store = ResponseStore(tmp_path / "data.db")
    store.initialize()
    with closing(sqlite3.connect(store.path)) as con:
        with con:
            assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 0
            con.execute(
                "INSERT INTO demo_submissions VALUES (?, ?, ?)",
                ("orphaned-nonce", "fingerprint", "nonexistent-response"),
            )
    with pytest.raises(ValueError, match="invalid response references"):
        store.initialize()


def test_template_has_individual_nonce_and_semantic_radio_groups():
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.globals["url_for"] = lambda endpoint, filename: "/static/" + filename
    html = env.get_template("index.html").render(
        csrf_token="stable-session-token",
        form_nonce="unique-form-token",
        form={},
        error=None,
    )
    soup = BeautifulSoup(html, "html.parser")
    assert soup.select_one('input[name="csrf_token"]')["value"] == "stable-session-token"
    assert soup.select_one('input[name="form_nonce"]')["value"] == "unique-form-token"
    for radio_name, expected_question in (
        ("roast_level", "Your go-to roast?"),
        ("milk_preference", "How do you take it?"),
    ):
        inputs = soup.select(f'input[type="radio"][name="{radio_name}"]')
        assert len(inputs) >= 3
        assert len({id(node.find_parent("fieldset")) for node in inputs}) == 1
        fieldset = inputs[0].find_parent("fieldset")
        assert fieldset is not None
        assert fieldset.find("legend").get_text(strip=True) == expected_question
    for label in soup.select("label[for]"):
        assert soup.find(id=label["for"]) is not None


def _contrast(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722

    light, dark = sorted([luminance(foreground), luminance(background)], reverse=True)
    return (light + 0.05) / (dark + 0.05)


@pytest.mark.parametrize(
    "selector,background",
    [
        (".score-foot", "#ffffff"),
        (".optional", "#fcfbf8"),
        (".technical-panel p", "#f2e9dc"),
        (".form-intro p", "#eeeee7"),
    ],
)
def test_audited_ui_text_contrast(selector, background):
    css = (ROOT / "static" / "style.css").read_text()
    declarations = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]+)\}", css)
    assert declarations is not None, selector
    color = re.search(r"(?m)\bcolor:\s*(#[0-9a-fA-F]{6})\s*;", declarations.group(1))
    assert color is not None, selector
    assert _contrast(color.group(1), background) >= 4.5, selector


def test_flask_json_provider_uses_modern_config():
    code = (ROOT / "__init__.py").read_text()
    assert "app.json.sort_keys = False" in code
    assert "JSON_SORT_KEYS" not in code


def test_clipboard_button_rapid_clicks_restore_original_label_and_status():
    js_path = ROOT / "static" / "app.js"
    # Execute production JS against a deterministic minimal DOM + virtual timer queue.
    node = r"""
        const assert = require('assert');
        const fs = require('fs');
        let next = 0;
        const timers = new Map();
        global.setTimeout = (callback) => { let key = ++next; timers.set(key, callback); return key; };
        global.clearTimeout = (key) => timers.delete(key);
        const button = {
          innerHTML: 'Copy example cart URL <span>↗</span>',
          dataset: { copy: 'https://shop.example/cart/123:1' },
          insertAdjacentElement(position, child) { this.status = child; },
          addEventListener(event, callback) { this.click = callback; },
          set textContent(value) { this.innerHTML = value; },
          get textContent() { return this.innerHTML; },
        };
        global.document = {
          querySelectorAll() { return [button]; },
          createElement() { return { setAttribute(key, value) {this[key] = value;} }; },
        };
        const written = [];
        Object.defineProperty(globalThis, 'navigator', { configurable: true,
          value: { clipboard: { writeText: async (value) => written.push(value) } } });
        const original = button.innerHTML;
        eval(fs.readFileSync(process.argv[1], 'utf8'));
        (async () => {
            await button.click(); await button.click();
            assert.equal(timers.size, 1);
            for (const callback of [...timers.values()]) callback();
            assert.equal(button.innerHTML, original);
            assert.equal(button.status.role, 'status');
            assert.equal(button.status['aria-live'], 'polite');
            assert.deepEqual(written, [button.dataset.copy, button.dataset.copy]);
        })().catch((err) => { console.error(err); process.exitCode = 1; });
    """
    try:
        result = subprocess.run(
            ["node", "-e", node, str(js_path)], capture_output=True, text=True, timeout=10, check=False
        )
    except FileNotFoundError:
        pytest.skip("Node.js is unavailable")
    assert result.returncode == 0, result.stderr


def test_mock_webhook_sender_ignores_configured_proxy(monkeypatch, capsys):
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            self.server.received.append(
                (
                    self.path,
                    self.headers.get("Typeform-Signature"),
                    self.rfile.read(int(self.headers.get("Content-Length", "0"))),
                )
            )
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"success"}')

        def log_message(self, *_args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    target.received = []
    proxy.received = []
    workers = [threading.Thread(target=s.serve_forever, daemon=True) for s in (target, proxy)]
    for worker in workers:
        worker.start()
    try:
        monkeypatch.setenv("TYPEFORM_WEBHOOK_SECRET", "test-loopback-only-secret-is-long-enough")
        monkeypatch.setenv("MOCK_WEBHOOK_URL", f"http://127.0.0.1:{target.server_port}/typeform/webhook")
        monkeypatch.setenv("http_proxy", f"http://127.0.0.1:{proxy.server_port}")
        monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{proxy.server_port}")
        monkeypatch.delenv("no_proxy", raising=False)
        monkeypatch.delenv("NO_PROXY", raising=False)
        send_mock_webhook.main()
        assert len(target.received) == 1
        assert not proxy.received
        assert target.received[0][0] == "/typeform/webhook"
        assert target.received[0][1].startswith("sha256=")
        assert target.received[0][2]
        assert "200" in capsys.readouterr().out
    finally:
        for server in (target, proxy):
            server.shutdown()
            server.server_close()
        for worker in workers:
            worker.join(timeout=3)
