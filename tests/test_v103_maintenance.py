"""Publication-consistency regressions for the v1.0.3 maintenance changes."""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_all_relative_markdown_links_exist_in_publication_tree():
    for document in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]:
        for destination in LINK.findall(document.read_text(encoding="utf-8")):
            if destination.startswith(("http:", "https:", "#", "mailto:")):
                continue
            path = destination.split("#", 1)[0].split("?", 1)[0]
            if path:
                assert (document.parent / path).exists(), f"{document}: broken link {destination}"


def test_sqlite_regression_helpers_manage_connection_lifetime():
    for name in ("test_storage.py", "test_runtime_certification.py"):
        source = (ROOT / "tests" / name).read_text(encoding="utf-8")
        assert "with sqlite3.connect(" not in source, name
        assert "with closing(sqlite3.connect(" in source, name


def test_current_release_status_is_explicit_and_versioned():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    doc = (ROOT / "docs/maintenance-verification-v1.0.3.md").read_text(encoding="utf-8")
    assert 'version = "1.0.3"' in pyproject
    assert "maintenance-verification-v1.0.3.md" in readme
    assert "full v1.0.3 runtime certification passed" in doc
