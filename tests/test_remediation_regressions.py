"""Adversarial regressions for the independent seventeen-finding audit."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest

from app.catalog import CatalogError, catalog_digest, validate_catalog
from app.config import Config
from app.preferences import ValidationError, normalize_preferences
from app.recommendations import ALGORITHM_VERSION, rank_recommendations, score_product
from app.security import validate_origin
from app.storage import ResponseConflict, ResponseStore, canonical_fingerprint


@pytest.mark.parametrize("caffeine", ["decaf", "regular", "high-caffeine"])
def test_all_three_recommendations_obey_selected_caffeine(catalog, caffeine):
    prefs = normalize_preferences(
        {
            "brew_method": "pour-over",
            "flavor_notes": ["fruity", "citrus"],
            "roast_level": "light",
            "caffeine_level": caffeine,
        }
    )
    results = rank_recommendations(prefs, catalog)
    assert len(results) == 3
    lookup = {item["key"]: item for item in catalog}
    for rec in results:
        assert caffeine in lookup[rec["product_key"]]["traits"]["caffeine_level"]


def test_regression_decaf_conflicting_preferences_never_returns_caffeinated(catalog):
    prefs = normalize_preferences(
        {
            "roast_level": "light",
            "brew_method": "pour-over",
            "flavor_notes": ["citrus", "fruity"],
            "caffeine_level": "decaf",
        }
    )
    results = rank_recommendations(prefs, catalog)
    assert {r["product_key"] for r in results} == {
        "balanced_decaf",
        "bright_mistline",
        "bold_midnight",
    }
    assert results[0]["product_key"] == "bright_mistline"


@pytest.mark.parametrize(
    "phrase",
    [
        "I hate bold coffee",
        "Please do NOT give me bold coffee",
        "I don't like bright roasts",
        "No balanced coffee, please",
    ],
)
def test_free_text_negation_does_not_affect_ranking(catalog, phrase):
    selected = {"roast_level": "medium", "flavor_notes": ["nutty"]}
    baseline = rank_recommendations(normalize_preferences(selected), catalog)
    with_note = rank_recommendations(normalize_preferences({**selected, "extra_notes": phrase}), catalog)
    assert baseline == with_note


def test_style_is_explicit_and_fully_reproducible(catalog):
    a = normalize_preferences({"style_preference": "bright", "extra_notes": "I actually dislike bright"})
    b = normalize_preferences({"style_preference": "bold", "extra_notes": "Please avoid bold"})
    assert a.public_dict() != b.public_dict()
    assert canonical_fingerprint(a) != canonical_fingerprint(b)
    assert rank_recommendations(a, catalog) != rank_recommendations(b, catalog)
    assert a.public_dict()["style_preference"] == "bright"


def test_free_text_alone_rejected():
    with pytest.raises(ValidationError, match="structured"):
        normalize_preferences({"extra_notes": "I need suggestions"})


def test_flavor_order_duplicate_replay_is_idempotent(tmp_path, catalog):
    store = ResponseStore(tmp_path / "idempotence.sqlite3")
    store.initialize()
    a = normalize_preferences({"flavor_notes": ["citrus", "fruity"]})
    b = normalize_preferences({"flavor_notes": ["fruity", "citrus", "fruity"]})
    digest = catalog_digest(catalog)
    assert canonical_fingerprint(a) == canonical_fingerprint(b)
    assert store.save_once("form-replay-001", a, rank_recommendations(a, catalog), digest)
    assert not store.save_once("form-replay-001", b, rank_recommendations(b, catalog), digest)
    assert store.get("form-replay-001")["preferences"]["flavor_notes"] == ["citrus", "fruity"]


def test_catalog_unicode_surrogates_and_formatting_rejected(catalog):
    for invalid in ("Roast\ud800", "Roast\u200b", "Roast\u202e", "Roast\n"):
        data = deepcopy(catalog)
        data[0]["title"] = invalid
        with pytest.raises(CatalogError, match="title"):
            validate_catalog(data)


def test_product_style_independent_of_key_name(catalog):
    prefs = normalize_preferences({"style_preference": "bright"})
    item = deepcopy(next(x for x in catalog if x["key"] == "bright_sunbeam"))
    assert score_product(item, prefs)[0] == 2
    item["key"] = "renamed_style_neutral"
    assert score_product(item, prefs)[0] == 2


def test_invalid_styles_and_insufficient_caffeine_coverage_rejected(catalog):
    data = deepcopy(catalog)
    data[0]["style"] = "ultra-bright"
    with pytest.raises(CatalogError, match="style"):
        validate_catalog(data)
    data = deepcopy(catalog)
    data[-1]["active"] = False
    data[-2]["active"] = False
    with pytest.raises(CatalogError, match="decaf"):
        validate_catalog(data)


def test_catalog_digest_stable_for_object_and_product_order(catalog):
    scrambled = [{key: value for key, value in reversed(list(p.items()))} for p in reversed(catalog)]
    assert catalog_digest(catalog) == catalog_digest(scrambled)
    changed = deepcopy(catalog)
    changed[0]["title"] += " Collection"
    assert catalog_digest(catalog) != catalog_digest(changed)


def test_persisted_snapshot_tracks_catalog_and_algorithm(tmp_path, catalog):
    store = ResponseStore(tmp_path / "history.sqlite3")
    store.initialize()
    prefs = normalize_preferences({"caffeine_level": "decaf"})
    digest = catalog_digest(catalog)
    original = rank_recommendations(prefs, catalog)
    assert store.save_once("history-0001", prefs, original, digest)
    assert store.get("history-0001")["catalog_digest"] == digest
    assert store.get("history-0001")["algorithm_version"] == ALGORITHM_VERSION
    modified = deepcopy(catalog)
    modified[0]["price"] = "99.99"
    assert catalog_digest(modified) != digest
    assert not store.save_once("history-0001", prefs, [], catalog_digest(modified))
    assert store.get("history-0001")["recommendations"] == original
    assert store.get("history-0001")["catalog_digest"] == digest


def test_legacy_database_schema_migrates_without_overwriting_old_snapshot(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("""CREATE TABLE responses (
                response_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL, preferences_json TEXT NOT NULL,
                recommendations_json TEXT NOT NULL)""")
            conn.execute(
                "INSERT INTO responses VALUES (?, ?, ?, ?, ?)",
                ("legacy-00001", "fingerprint", "past", "{}", "[]"),
            )
    store = ResponseStore(path)
    store.initialize()
    record = store.get("legacy-00001")
    assert record["catalog_digest"] == "legacy-unversioned"
    assert record["algorithm_version"] == "legacy-unversioned"
    assert record["recommendations"] == []


def test_preexisting_sqlite_symlink_from_environment_is_rejected(monkeypatch, tmp_path):
    target = tmp_path / "target.sqlite3"
    link = tmp_path / "alias.sqlite3"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    monkeypatch.setenv("APP_DB_PATH", str(link))
    cfg = Config.from_env()
    assert cfg.db_path == link
    with pytest.raises(ValueError, match="symbolic"):
        ResponseStore(cfg.db_path).initialize()
    assert not target.exists()


def test_parent_directory_symlink_rejected(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="symbolic"):
        ResponseStore(alias / "db.sqlite3").initialize()
    assert not (real_dir / "db.sqlite3").exists()


@pytest.mark.parametrize(
    "invalid",
    [
        "https://.",
        "https://bad..example",
        "https://-bad.example",
        "https://example.com-",
        "https://example.com\\@evil.example",
        "https://example.com:444",
        "https://example.com:garbage",
        "https://example.com/#fragment",
        "https://example.com/x",
    ],
)
def test_cors_rejects_invalid_origins(invalid):
    with pytest.raises(ValueError):
        validate_origin(invalid)


def test_cors_normalizes_default_port_and_case():
    assert validate_origin("https://EXAMPLE.com:443") == "https://example.com"
    assert validate_origin("https://example.com/") == "https://example.com"
    assert validate_origin("https://example.com") == "https://example.com"


def test_zero_score_alternatives_are_explicit(catalog):
    prefs = normalize_preferences({"milk_preference": "other"})
    results = rank_recommendations(prefs, catalog)
    assert any(item["score"] == 0 for item in results)
    assert all(item["match_quality"] == ("matched" if item["score"] else "exploratory") for item in results)
    assert all("none of your selected" in item["why"] for item in results if not item["score"])


def test_local_form_nonce_is_atomic_under_concurrent_requests(tmp_path, catalog):
    store = ResponseStore(tmp_path / "responses.sqlite3")
    store.initialize()
    prefs = normalize_preferences({"caffeine_level": "decaf", "flavor_notes": ["chocolatey"]})
    recommendations = rank_recommendations(prefs, catalog)
    digest = catalog_digest(catalog)

    def submit(_):
        return store.save_form_once(
            "unique-high-entropy-demo-nonce-001", f"fresh-response-{_:04d}", prefs, recommendations, digest
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        response_ids = list(pool.map(submit, range(30)))
    assert len(set(response_ids)) == 1
    with closing(sqlite3.connect(store.path)) as conn:
        assert conn.execute("SELECT count(*) FROM responses").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM demo_submissions").fetchone()[0] == 1


def test_local_form_nonce_changed_answers_rejected(tmp_path, catalog):
    store = ResponseStore(tmp_path / "responses.sqlite3")
    store.initialize()
    first = normalize_preferences({"roast_level": "light"})
    other = normalize_preferences({"roast_level": "dark"})
    digest = catalog_digest(catalog)
    store.save_form_once(
        "nonce-1234567890", "first-resp-001", first, rank_recommendations(first, catalog), digest
    )
    with pytest.raises(ResponseConflict):
        store.save_form_once(
            "nonce-1234567890", "second-resp-002", other, rank_recommendations(other, catalog), digest
        )


def _luminance(rgb: str) -> float:
    channel = [int(rgb[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    adjusted = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channel]
    return 0.2126 * adjusted[0] + 0.7152 * adjusted[1] + 0.0722 * adjusted[2]


def _contrast(a: str, b: str) -> float:
    x, y = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def test_fixed_ui_muted_text_passes_wcag_aa_normal_text():
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "style.css").read_text()
    for foreground, background in (
        ("#586259", "#fcfbf8"),
        ("#596359", "#ffffff"),
        ("#596359", "#fcfbf8"),
        ("#516154", "#eceee7"),
    ):
        assert foreground in css
        assert _contrast(foreground, background) >= 4.5
