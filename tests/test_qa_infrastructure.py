"""Regression checks for the independent v1.0.1 QA/release audit."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from threading import Thread

from scripts.loopback_http import loopback_opener
from scripts.verify_release import ROOT, isolated_smoke_environment


def test_proxy_settings_cannot_intercept_local_http(monkeypatch):
    hits = {"direct": 0, "proxy": 0}

    def server(kind):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits[kind] += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(kind.encode())

            def log_message(self, *_args):
                pass

        return ThreadingHTTPServer(("127.0.0.1", 0), Handler)

    direct = server("direct")
    proxy = server("proxy")
    direct_thread = Thread(target=direct.serve_forever, daemon=True)
    proxy_thread = Thread(target=proxy.serve_forever, daemon=True)
    direct_thread.start()
    proxy_thread.start()
    try:
        proxy_url = f"http://127.0.0.1:{proxy.server_port}"
        monkeypatch.setenv("HTTP_PROXY", proxy_url)
        monkeypatch.setenv("http_proxy", proxy_url)
        monkeypatch.setenv("HTTPS_PROXY", proxy_url)
        monkeypatch.setenv("https_proxy", proxy_url)
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("no_proxy", "")
        with loopback_opener().open(f"http://127.0.0.1:{direct.server_port}/health", timeout=3) as response:
            assert response.read() == b"direct"
        assert hits == {"direct": 1, "proxy": 0}
    finally:
        direct.shutdown()
        proxy.shutdown()
        direct.server_close()
        proxy.server_close()
        direct_thread.join(timeout=2)
        proxy_thread.join(timeout=2)


def test_runtime_http_helpers_use_proxy_free_opener():
    for filename in ("test_live_http.py", "test_waitress_entrypoint.py"):
        text = (ROOT / "tests" / filename).read_text(encoding="utf-8")
        assert "loopback_opener(" in text
        assert "from scripts.loopback_http import loopback_opener" in text
        assert "urlopen(" not in text


def test_fresh_wheel_smoke_removes_application_overrides(monkeypatch, tmp_path):
    injected = {
        "APP_CATALOG_PATH": str(tmp_path / "foreign.json"),
        "APP_MODE": "production",
        "TYPEFORM_WEBHOOK_SECRET": "do-not-inherit-secret-0123456789",
        "TYPEFORM_FORM_ID": "BAD_FORM",
        "COFFEE_BROWSER_PATH": "/fake/browser",
        "ALLOWED_ORIGINS": "https://foreign.example",
        "FLASK_APP": "wrong:app",
        "PYTHONPATH": str(tmp_path / "injection"),
        "PYTHONHOME": str(tmp_path / "python-home"),
        "PORT": "8888",
    }
    for k, v in injected.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("QA_INHERITED_SENTINEL", "retained")
    clean = isolated_smoke_environment(tmp_path / "clean.sqlite3")
    assert all(k not in clean for k in injected if k != "APP_MODE")
    assert clean["APP_MODE"] == "local"
    assert clean["APP_DB_PATH"] == str(tmp_path / "clean.sqlite3")
    assert clean["QA_INHERITED_SENTINEL"] == "retained"


def test_fresh_install_probes_the_installed_catalog(monkeypatch, tmp_path):
    from scripts import verify_release as gate

    monkeypatch.setenv("APP_CATALOG_PATH", str(tmp_path / "bad.json"))
    calls = []

    def run(name, cmd, **kwargs):
        calls.append((name, cmd, kwargs))
        if name == "fresh_wheel_build":
            dest = Path(cmd[cmd.index("--outdir") + 1])
            dest.mkdir(parents=True)
            (dest / "coffee_recommendation_prototype-1.0.3-py3-none-any.whl").write_bytes(b"fixture")
        return {"name": name, "status": "passed"}

    monkeypatch.setattr(gate, "run", run)
    assert gate.fresh_install_check()["status"] == "passed"
    health = next((cmd, kwargs) for name, cmd, kwargs in calls if name == "fresh_health")
    assert "APP_CATALOG_PATH" not in health[1]["env"]
    assert "Config.from_env().catalog_path == catalog" in "".join(health[0])
    install = next(cmd for name, cmd, _ in calls if name == "fresh_install")
    assert "-c" in install and str(ROOT / "requirements-verified.txt") in install


def test_docker_qa_image_has_node_and_pinned_base():
    docker = (ROOT / "Dockerfile.verify").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.13\.13-slim-bookworm@sha256:[a-f0-9]{64}$", docker, re.M)
    assert "apt-get install -y --no-install-recommends nodejs" in docker
    assert "node --version" in docker
    assert "-c requirements-verified.txt" in docker


def test_ci_explicit_runner_and_qa_constraint_input():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert workflow.count("runs-on: ubuntu-24.04") == 2
    assert "ubuntu-latest" not in workflow
    assert workflow.count("-c requirements-verified.txt") >= 4
    assert "SOURCE_DATE_EPOCH=1762819200" in workflow


def test_release_wheel_uses_stable_epoch():
    verifier = (ROOT / "scripts/verify_release.py").read_text(encoding="utf-8")
    assert verifier.count('"SOURCE_DATE_EPOCH": "1762819200"') >= 2
