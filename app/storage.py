"""SQLite snapshots with transaction-safe idempotency and no raw customer data."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Iterator

from .preferences import Preferences
from .recommendations import ALGORITHM_VERSION

LEGACY_DIGEST = "legacy-unversioned"


class ResponseConflict(Exception):
    """A response ID or local form nonce was reused with changed preferences."""


def canonical_fingerprint(prefs: Preferences) -> str:
    """Order-insensitive flavor choices; no free text is stored or fingerprinted."""
    values = prefs.public_dict()
    values["flavor_notes"] = sorted(set(values["flavor_notes"]))
    packed = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


class ResponseStore:
    def __init__(self, path: Path):
        # Never resolve() here: it would dereference a symlink before validation.
        self.path = Path(os.path.abspath(os.fspath(path.expanduser())))

    def _reject_symlinks(self) -> None:
        """Reject existing symlinks in the DB path and its parent chain.

        This assumes the demo directory is locally controlled. It does not
        purport to defend concurrent malicious filesystem modifications.
        """
        part = self.path
        while True:
            if part.is_symlink():
                raise ValueError("Database path must not include a symbolic link.")
            if part == part.parent:
                break
            part = part.parent

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._reject_symlinks()
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA foreign_keys = ON")
            if con.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise RuntimeError("SQLite foreign-key enforcement is unavailable.")
            with con:
                yield con
        finally:
            con.close()

    def initialize(self) -> None:
        self._reject_symlinks()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._reject_symlinks()
        with self._connection() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS responses (
                response_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                preferences_json TEXT NOT NULL,
                recommendations_json TEXT NOT NULL,
                catalog_digest TEXT NOT NULL DEFAULT 'legacy-unversioned',
                algorithm_version TEXT NOT NULL DEFAULT 'legacy-unversioned'
            )""")
            existing = {row["name"] for row in con.execute("PRAGMA table_info(responses)")}
            for field in ("catalog_digest", "algorithm_version"):
                if field not in existing:
                    con.execute(
                        f"ALTER TABLE responses ADD COLUMN {field} TEXT NOT NULL DEFAULT 'legacy-unversioned'"
                    )
            con.execute("""CREATE TABLE IF NOT EXISTS local_session_key (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                secret BLOB NOT NULL CHECK (length(secret) = 32)
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS demo_submissions (
                nonce_hash TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                response_id TEXT NOT NULL UNIQUE REFERENCES responses(response_id)
            )""")
            if con.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Existing database contains invalid response references.")
        if os.name == "posix":
            os.chmod(self.path, 0o600)

    def get_or_create_session_key(self) -> bytes:
        """Return the same local Flask session key across process restarts.

        SQLite's write transaction serializes first-start creation across workers.
        The key lives only in the owner-controlled, mode-0600 database file;
        it is never committed or included in the publication archive.
        """
        with self._connection() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT OR IGNORE INTO local_session_key (singleton, secret) VALUES (1, ?)",
                (secrets.token_bytes(32),),
            )
            row = con.execute("SELECT secret FROM local_session_key WHERE singleton = 1").fetchone()
            if row is None or not isinstance(row["secret"], bytes) or len(row["secret"]) != 32:
                raise ValueError("Invalid local session key in database.")
            return row["secret"]

    @staticmethod
    def _insert(
        con: sqlite3.Connection,
        response_id: str,
        fingerprint: str,
        prefs: Preferences,
        recommendations: list[dict[str, Any]],
        digest: str,
    ) -> None:
        con.execute(
            "INSERT INTO responses (response_id, fingerprint, created_at, preferences_json, "
            "recommendations_json, catalog_digest, algorithm_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                response_id,
                fingerprint,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(prefs.public_dict(), sort_keys=True),
                json.dumps(recommendations, sort_keys=True),
                digest,
                ALGORITHM_VERSION,
            ),
        )

    def save_once(
        self,
        response_id: str,
        prefs: Preferences,
        recommendations: list[dict[str, Any]],
        digest: str = LEGACY_DIGEST,
    ) -> bool:
        """True on first save, False for equivalent retry, conflict for modified answers.

        Existing response snapshots intentionally survive catalog changes.
        """
        fingerprint = canonical_fingerprint(prefs)
        with self._connection() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute(
                "SELECT fingerprint FROM responses WHERE response_id = ?", (response_id,)
            ).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise ResponseConflict("Response identifier already exists with different preferences.")
                return False
            self._insert(con, response_id, fingerprint, prefs, recommendations, digest)
            return True

    def save_form_once(
        self,
        nonce: str,
        response_id: str,
        prefs: Preferences,
        recommendations: list[dict[str, Any]],
        digest: str,
    ) -> str:
        """Return the stable response ID for concurrent local form retries.

        One transaction protects both the recommendation record and the nonce.
        A SHA-256 hash of the high-entropy nonce is stored instead of the token.
        """
        nonce_hash = hashlib.sha256(nonce.encode("ascii")).hexdigest()
        fingerprint = canonical_fingerprint(prefs)
        with self._connection() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute(
                "SELECT response_id, fingerprint FROM demo_submissions WHERE nonce_hash = ?", (nonce_hash,)
            ).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise ResponseConflict("Form nonce already used for different preferences.")
                return str(existing["response_id"])
            self._insert(con, response_id, fingerprint, prefs, recommendations, digest)
            con.execute(
                "INSERT INTO demo_submissions (nonce_hash, fingerprint, response_id) VALUES (?, ?, ?)",
                (nonce_hash, fingerprint, response_id),
            )
            return response_id

    def get(self, response_id: str) -> dict[str, Any] | None:
        with self._connection() as con:
            row = con.execute(
                "SELECT response_id, created_at, preferences_json, recommendations_json, "
                "catalog_digest, algorithm_version FROM responses WHERE response_id=?",
                (response_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "response_id": row["response_id"],
            "status": "ready",
            "created_at": row["created_at"],
            "catalog_digest": row["catalog_digest"],
            "algorithm_version": row["algorithm_version"],
            "preferences": json.loads(row["preferences_json"]),
            "recommendations": json.loads(row["recommendations_json"]),
            "cart_preview_only": True,
        }
