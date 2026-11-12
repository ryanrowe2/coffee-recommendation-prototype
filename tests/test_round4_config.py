"""Regression tests for external-integration configuration and webhook contracts."""

from copy import deepcopy

import pytest

from app.config import Config
from app.preferences import ValidationError, normalize_typeform_payload


@pytest.mark.parametrize("secret", [" " * 30, "short", "x" * 24 + "\n", "x" * 24 + " "])
def test_reject_unreliable_signature_secrets(monkeypatch, secret):
    monkeypatch.setenv("TYPEFORM_WEBHOOK_SECRET", secret)
    with pytest.raises(ValueError, match="TYPEFORM_WEBHOOK_SECRET"):
        Config.from_env()


@pytest.mark.parametrize("form_id", ["invalid form", "bad/form", "\x01", "x" * 129])
def test_reject_malformed_configured_typeform_id(monkeypatch, form_id):
    monkeypatch.setenv("TYPEFORM_FORM_ID", form_id)
    with pytest.raises(ValueError, match="TYPEFORM_FORM_ID"):
        Config.from_env()


@pytest.mark.parametrize("key", ["APP_DB_PATH", "APP_CATALOG_PATH"])
def test_reject_empty_storage_configuration(monkeypatch, key):
    monkeypatch.setenv(key, "  ")
    with pytest.raises(ValueError, match="must not be empty"):
        Config.from_env()


def test_valid_configured_typeform_id_and_secret(monkeypatch):
    monkeypatch.setenv("TYPEFORM_WEBHOOK_SECRET", "a-very-long-random-test-secret-2026")
    monkeypatch.setenv("TYPEFORM_FORM_ID", "DEMO_COFFEE_FORM")
    cfg = Config.from_env()
    assert cfg.form_id == "DEMO_COFFEE_FORM"
    assert cfg.webhook_secret == "a-very-long-random-test-secret-2026"


def test_unicode_signature_secret_is_valid(monkeypatch):
    monkeypatch.setenv("TYPEFORM_WEBHOOK_SECRET", "clé-sécurisée-avec-longueur-suffisante")
    assert Config.from_env().webhook_secret.startswith("clé-")


def test_typeform_event_type_must_be_explicit(example_payload):
    payload = deepcopy(example_payload)
    del payload["event_type"]
    with pytest.raises(ValidationError, match="event type"):
        normalize_typeform_payload(payload)
