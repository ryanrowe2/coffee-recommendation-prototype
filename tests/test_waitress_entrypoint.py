"""Launch the actual advertised `python -m app` Waitress entry point."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from scripts.loopback_http import loopback_opener

import pytest

from app.config import ROOT

pytest.importorskip("flask", reason="Flask required to launch the Waitress app")
pytest.importorskip("waitress", reason="Waitress required to launch the advertised entry point")


def test_waitress_subprocess_starts_and_serves_http(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = os.environ.copy()
    env.update(
        {
            "APP_MODE": "local",
            "PORT": str(port),
            "APP_DB_PATH": str(tmp_path / "waitress.sqlite3"),
            "APP_CATALOG_PATH": str(ROOT / "data" / "catalog.json"),
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        }
    )
    env.pop("TYPEFORM_WEBHOOK_SECRET", None)
    process = subprocess.Popen(
        [sys.executable, "-m", "app"],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}/health"
    opener = loopback_opener()
    try:
        last_error = None
        for _ in range(65):
            if process.poll() is not None:
                break
            try:
                with opener.open(url, timeout=0.25) as response:
                    assert response.status == 200
                    assert json.load(response)["status"] == "ok"
                    return
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                time.sleep(0.1)
        raise AssertionError(f"Waitress startup/HTTP failed: {last_error}; exit code {process.poll()}")
    finally:
        process.terminate()
        try:
            output = process.communicate(timeout=3)[0]
        except subprocess.TimeoutExpired:
            process.kill()
            output = process.communicate(timeout=2)[0]
        assert b"Traceback" not in output, output.decode("utf-8", errors="replace")
