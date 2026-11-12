"""Send a signed, synthetic Typeform payload to a loopback Flask server.

Usage:
    TYPEFORM_WEBHOOK_SECRET='my-long-demo-secret-123456789' python scripts/send_mock_webhook.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate_mock_url(url: str) -> str:
    """Prevent a configurable demo sender from leaking signatures to remote hosts."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Mock webhook URL has an invalid port.") from exc
    if (
        "?" in url
        or "#" in url
        or parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or not 1024 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/typeform/webhook"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Mock sender requires http://127.0.0.1:<port>/typeform/webhook.")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def main() -> None:
    secret = os.environ.get("TYPEFORM_WEBHOOK_SECRET", "")
    if len(secret) < 24:
        raise SystemExit("Set TYPEFORM_WEBHOOK_SECRET to a private value of at least 24 characters.")
    try:
        target = validate_mock_url(
            os.environ.get("MOCK_WEBHOOK_URL", "http://127.0.0.1:5050/typeform/webhook")
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    body = (ROOT / "examples" / "sample_submission.json").read_bytes()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    signature = "sha256=" + base64.b64encode(digest).decode()
    request = urllib.request.Request(
        target,
        body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Typeform-Signature": signature,
        },
    )
    # Never inherit http_proxy/HTTP_PROXY: signed mock payloads must remain loopback-only.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    try:
        with opener.open(request, timeout=10) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.code, exc.read().decode())
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
