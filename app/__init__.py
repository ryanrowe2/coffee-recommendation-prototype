"""Application factory for the standalone coffee recommendation prototype."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .catalog import catalog_digest, load_catalog
from .config import Config
from .storage import ResponseStore

if TYPE_CHECKING:
    from flask import Flask


def create_app(config: Config | None = None) -> "Flask":
    from flask import Flask

    cfg = config or Config.from_env()
    catalog = load_catalog(cfg.catalog_path)
    version = catalog_digest(catalog)
    store = ResponseStore(cfg.db_path)
    store.initialize()

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.update(
        SECRET_KEY=store.get_or_create_session_key(),
        TRUSTED_HOSTS=["127.0.0.1", "localhost"],
        MAX_CONTENT_LENGTH=cfg.max_request_bytes,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=(cfg.mode == "production"),
    )
    app.json.sort_keys = False
    app.extensions["coffee_config"] = cfg
    app.extensions["coffee_catalog"] = catalog
    app.extensions["coffee_catalog_digest"] = version
    app.extensions["coffee_store"] = store
    from .routes import register_routes

    register_routes(app)
    app.logger.setLevel(logging.INFO)
    return app
