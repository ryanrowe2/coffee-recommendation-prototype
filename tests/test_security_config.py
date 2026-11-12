import base64
import hashlib
import hmac
import pytest

from app.config import Config
from app.security import verify_typeform_signature, validate_origin


def test_valid_signature():
    body = b'{"coffee": "light"}'
    secret = "strong-secret"
    header = "sha256=" + base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    assert verify_typeform_signature(body, header, secret)
    assert not verify_typeform_signature(body + b" ", header, secret)


@pytest.mark.parametrize(
    "header", [None, "", "sha256=not valid!", "sha256=", "sha1=abc", "sha256=" + "X" * 300]
)
def test_invalid_signature(header):
    assert not verify_typeform_signature(b"hello", header, "strong-secret")


def test_missing_secret_rejects_even_wellformed_signature():
    assert not verify_typeform_signature(b"hello", "sha256=" + base64.b64encode(b"x" * 32).decode(), "")


def test_secure_origins():
    assert validate_origin("https://example.com/") == "https://example.com"


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "http://example.com",
        "https://user:pass@example.com",
        "https://@example.com",
        "https://:@example.com",
        "https://@127.0.0.1",
        "https://example.com:",
        "https://example.com:/",
        "https://[::1]:",
        "https://example.com/path",
        "https://example.com?q=1",
        "https://example.com:444",
        "file:///tmp/file",
        "javascript:alert(1)",
    ],
)
def test_bad_origins(origin):
    with pytest.raises(ValueError):
        validate_origin(origin)


@pytest.mark.parametrize("invalid", ["https://@example.com", "https://example.com:"])
def test_origin_configuration_fails_on_noncanonical_authority(monkeypatch, invalid):
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("ALLOWED_ORIGINS", invalid)
    with pytest.raises(ValueError):
        Config.from_env()


def test_local_mode_defaults(monkeypatch):
    for key in ("APP_MODE", "TYPEFORM_WEBHOOK_SECRET", "TYPEFORM_FORM_ID", "ALLOWED_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    config = Config.from_env()
    assert config.mode == "local" and config.webhook_secret == "" and config.allowed_origins == ()


def test_production_requires_secret_and_form(monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.delenv("TYPEFORM_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("TYPEFORM_FORM_ID", raising=False)
    with pytest.raises(ValueError):
        Config.from_env()


def test_production_valid_with_explicit_config(monkeypatch):
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("TYPEFORM_WEBHOOK_SECRET", "a" * 24)
    monkeypatch.setenv("TYPEFORM_FORM_ID", "123")
    assert Config.from_env().mode == "production"


def test_config_rejects_bad_cors(monkeypatch):
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    with pytest.raises(ValueError):
        Config.from_env()


def test_invalid_port_rejected_before_server_start(monkeypatch):
    from app.__main__ import main

    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("PORT", "80")
    with pytest.raises(ValueError, match="PORT"):
        main()


def test_unsupported_production_server_preflight(monkeypatch):
    from app.__main__ import main

    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("TYPEFORM_WEBHOOK_SECRET", "b" * 32)
    monkeypatch.setenv("TYPEFORM_FORM_ID", "DEMO_FORM")
    monkeypatch.setenv("PORT", "5050")
    with pytest.raises(RuntimeError, match="no supported production"):
        main()


def test_local_weak_webhook_secret_rejected(monkeypatch):
    monkeypatch.setenv("APP_MODE", "local")
    monkeypatch.setenv("TYPEFORM_WEBHOOK_SECRET", "short")
    with pytest.raises(ValueError, match="24 characters"):
        Config.from_env()
