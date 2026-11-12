"""Test fixtures deliberately avoid network and external store credentials."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.catalog import load_catalog
from app.config import ROOT, Config


@pytest.fixture
def catalog():
    return load_catalog(ROOT / "data" / "catalog.json")


@pytest.fixture
def example_payload():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "examples" / "sample_submission.json").read_text()
    )


@pytest.fixture
def local_config(tmp_path):
    return Config(
        mode="local",
        db_path=tmp_path / "db.sqlite3",
        catalog_path=ROOT / "data" / "catalog.json",
        form_id="DEMO_COFFEE_FORM",
        webhook_secret="this-is-a-local-test-secret-123456",
        allowed_origins=(),
    )
