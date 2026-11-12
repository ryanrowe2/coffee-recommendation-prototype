"""Serve local demo with Waitress on the loopback interface."""

from __future__ import annotations

import os

from . import create_app
from .config import Config


def main() -> None:
    cfg = Config.from_env()
    port = int(os.environ.get("PORT", "5050"))
    if not 1024 <= port <= 65535:
        raise ValueError("PORT must be between 1024 and 65535.")
    if cfg.mode == "production":
        raise RuntimeError("This portfolio demo has no supported production deployment entry point.")
    from waitress import serve

    app = create_app(cfg)
    print(f"Coffee demo: http://127.0.0.1:{port}", flush=True)
    serve(app, host="127.0.0.1", port=port, threads=4)


if __name__ == "__main__":
    main()
