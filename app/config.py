"""Explicit, testable application configuration; conservative integration defaults."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from .security import validate_origin

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    mode: str
    db_path: Path
    catalog_path: Path
    form_id: str | None
    webhook_secret: str
    allowed_origins: tuple[str, ...]
    max_request_bytes: int = 65536

    @classmethod
    def from_env(cls) -> "Config":
        mode = os.environ.get("APP_MODE", "local").strip().lower()
        if mode not in {"local", "production"}:
            raise ValueError("APP_MODE must be local or production.")
        secret = os.environ.get("TYPEFORM_WEBHOOK_SECRET", "")
        form_id = os.environ.get("TYPEFORM_FORM_ID") or None
        if secret and (
            len(secret) < 24 or secret != secret.strip() or any(not char.isprintable() for char in secret)
        ):
            raise ValueError(
                "TYPEFORM_WEBHOOK_SECRET must contain 24 characters minimum, all printable and without surrounding whitespace."
            )
        if form_id is not None and (not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", form_id)):
            raise ValueError(
                "TYPEFORM_FORM_ID must contain 1–128 ASCII letters, numbers, underscores or hyphens."
            )
        if mode == "production" and (not secret or not form_id):
            raise ValueError("Production requires TYPEFORM_WEBHOOK_SECRET and TYPEFORM_FORM_ID.")
        db_value = os.environ.get("APP_DB_PATH", ".local_data/recommendations.sqlite3")
        catalog_value = os.environ.get("APP_CATALOG_PATH", str(ROOT / "data" / "catalog.json"))
        if not db_value.strip() or not catalog_value.strip():
            raise ValueError("APP_DB_PATH and APP_CATALOG_PATH must not be empty.")
        origins = tuple(filter(None, (p.strip() for p in os.environ.get("ALLOWED_ORIGINS", "").split(","))))
        if len(origins) > 10:
            raise ValueError("Too many CORS origins.")
        return cls(
            mode=mode,
            db_path=Path(os.path.abspath(os.path.expanduser(db_value))),
            catalog_path=Path(catalog_value).expanduser().resolve(),
            form_id=form_id,
            webhook_secret=secret,
            allowed_origins=tuple(validate_origin(origin) for origin in origins),
        )
