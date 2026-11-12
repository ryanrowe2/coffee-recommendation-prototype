import sqlite3
from contextlib import closing
import pytest

from app.preferences import normalize_preferences
from app.recommendations import rank_recommendations
from app.storage import ResponseConflict, ResponseStore


def test_storage_insert_replay_retrieve(tmp_path, catalog):
    store = ResponseStore(tmp_path / "db" / "responses.sqlite3")
    store.initialize()
    p = normalize_preferences({"roast_level": "dark", "extra_notes": "john@example.com"})
    r = rank_recommendations(p, catalog)
    assert store.save_once("response-0001", p, r) is True
    assert store.save_once("response-0001", p, r) is False
    record = store.get("response-0001")
    assert record["recommendations"] == r
    assert record["cart_preview_only"] is True
    assert store.get("unknown-0001") is None
    assert "john@example.com" not in (tmp_path / "db" / "responses.sqlite3").read_bytes().decode("latin1")


def test_conflicting_replay_preserves_original(tmp_path, catalog):
    store = ResponseStore(tmp_path / "app.sqlite3")
    store.initialize()
    a = normalize_preferences({"roast_level": "light"})
    b = normalize_preferences({"roast_level": "dark"})
    store.save_once("response-0002", a, rank_recommendations(a, catalog))
    with pytest.raises(ResponseConflict):
        store.save_once("response-0002", b, rank_recommendations(b, catalog))
    assert store.get("response-0002")["preferences"]["roast_level"] == "light"


def test_restart_persistence(tmp_path, catalog):
    path = tmp_path / "app.sqlite3"
    store = ResponseStore(path)
    store.initialize()
    p = normalize_preferences({"flavor_notes": ["caramel"]})
    store.save_once("response-0003", p, rank_recommendations(p, catalog))
    reopened = ResponseStore(path)
    reopened.initialize()
    assert reopened.get("response-0003")["recommendations"][0]["rank"] == 1
    assert reopened.save_once("response-0003", p, []) is False


def test_sql_injection_id_treated_as_data(tmp_path):
    store = ResponseStore(tmp_path / "db.sqlite3")
    store.initialize()
    assert store.get("' OR 1=1 --") is None
    conn = sqlite3.connect(store.path)
    try:
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name='responses'").fetchone()[0] == 1
    finally:
        conn.close()


def test_concurrent_duplicate_writes_are_serialized(tmp_path, catalog):
    from concurrent.futures import ThreadPoolExecutor

    store = ResponseStore(tmp_path / "db.sqlite3")
    store.initialize()
    p = normalize_preferences({"roast_level": "medium"})
    result = rank_recommendations(p, catalog)
    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(lambda _: store.save_once("concurrent-0001", p, result), range(16)))
    assert created.count(True) == 1
    assert created.count(False) == 15
    assert store.get("concurrent-0001")["recommendations"] == result


def test_private_notes_neither_persisted_nor_hashed(tmp_path, catalog):
    path = tmp_path / "private.sqlite3"
    store = ResponseStore(path)
    store.initialize()
    a = normalize_preferences({"roast_level": "dark", "extra_notes": "secret@example.com"})
    b = normalize_preferences({"roast_level": "dark", "extra_notes": "another@example.com"})
    result = rank_recommendations(a, catalog)
    assert store.save_once("private000001", a, result)
    assert store.save_once("private000001", b, result) is False
    assert b"secret@example.com" not in path.read_bytes()
    assert b"another@example.com" not in path.read_bytes()


def test_different_explicit_styles_conflict(tmp_path, catalog):
    store = ResponseStore(tmp_path / "private.sqlite3")
    store.initialize()
    bright = normalize_preferences({"style_preference": "bright"})
    bold = normalize_preferences({"style_preference": "bold"})
    store.save_once("style-000001", bright, rank_recommendations(bright, catalog))
    with pytest.raises(ResponseConflict):
        store.save_once("style-000001", bold, rank_recommendations(bold, catalog))


def test_db_rejects_symlink(tmp_path):
    target = tmp_path / "existing.sqlite3"
    target.write_bytes(b"do not modify")
    link = tmp_path / "linked.sqlite3"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unsupported")
    with pytest.raises(ValueError, match="symbolic"):
        ResponseStore(link).initialize()
    assert target.read_bytes() == b"do not modify"


def test_db_file_is_private_when_posix(tmp_path):
    import os

    if os.name != "posix":
        pytest.skip("POSIX permissions only")
    path = tmp_path / "records.sqlite3"
    ResponseStore(path).initialize()
    assert path.stat().st_mode & 0o077 == 0


def test_local_session_key_persists_across_store_restarts(tmp_path):
    from app.storage import ResponseStore

    path = tmp_path / "persistent.sqlite3"
    first = ResponseStore(path)
    first.initialize()
    key = first.get_or_create_session_key()
    assert isinstance(key, bytes) and len(key) == 32
    assert first.get_or_create_session_key() == key

    second = ResponseStore(path)
    second.initialize()
    assert second.get_or_create_session_key() == key

    separate = ResponseStore(tmp_path / "other.sqlite3")
    separate.initialize()
    assert separate.get_or_create_session_key() != key
    if __import__("os").name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_local_session_key_creation_is_safe_under_concurrency(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from app.storage import ResponseStore

    path = tmp_path / "concurrent.sqlite3"
    ResponseStore(path).initialize()

    def read_key(_):
        return ResponseStore(path).get_or_create_session_key()

    with ThreadPoolExecutor(max_workers=8) as pool:
        keys = list(pool.map(read_key, range(24)))
    assert len(set(keys)) == 1


def test_corrupted_local_session_key_fails_closed(tmp_path):
    import sqlite3
    import pytest
    from app.storage import ResponseStore

    path = tmp_path / "invalid.sqlite3"
    store = ResponseStore(path)
    store.initialize()
    store.get_or_create_session_key()
    with closing(sqlite3.connect(path)) as con:
        con.execute("PRAGMA ignore_check_constraints = ON")
        con.execute("UPDATE local_session_key SET secret = ? WHERE singleton = 1", (b"bad",))
        con.commit()
    with pytest.raises(ValueError, match="Invalid local session key"):
        store.get_or_create_session_key()
