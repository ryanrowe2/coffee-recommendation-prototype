"""HTTP endpoints for the local browser experience and signed Typeform integration."""

from __future__ import annotations

import secrets
from typing import Any

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

from .preferences import (
    ValidationError,
    normalize_preferences,
    normalize_typeform_payload,
    validate_response_id,
)
from .recommendations import ALGORITHM_VERSION, cart_preview_url, rank_recommendations
from .security import validate_origin, verify_typeform_signature
from .storage import ResponseConflict


def register_routes(app: Flask) -> None:
    cfg = app.extensions["coffee_config"]
    catalog = app.extensions["coffee_catalog"]
    store = app.extensions["coffee_store"]
    digest = app.extensions["coffee_catalog_digest"]
    allowed_origins = frozenset(validate_origin(origin) for origin in cfg.allowed_origins)

    @app.after_request
    def security_headers(response: Any) -> Any:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        if request.path in ("/", "/demo/submit", "/typeform/webhook") or request.path.startswith(
            ("/api/", "/results/")
        ):
            response.headers["Cache-Control"] = "no-store"
        origin = request.headers.get("Origin")
        if (
            origin
            and request.method in {"GET", "OPTIONS"}
            and request.path.startswith("/api/recommendations/")
            and request.path != "/api/recommendations/preview"
        ):
            try:
                canonical_origin = validate_origin(origin)
            except ValueError:
                canonical_origin = None
            if canonical_origin in allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = canonical_origin
                response.headers["Vary"] = "Origin"
                response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.errorhandler(413)
    def oversized_request(_: Any) -> tuple[Any, int]:
        return jsonify({"status": "error", "message": "Request body is too large."}), 413

    @app.errorhandler(500)
    def unexpected_error(_: Any) -> tuple[Any, int]:
        app.logger.exception("Internal request failure")
        return jsonify({"status": "error", "message": "An internal error occurred."}), 500

    @app.get("/health")
    def health() -> tuple[Any, int]:
        return jsonify({"status": "ok", "service": "coffee-recommendation-prototype", "mode": cfg.mode}), 200

    @app.get("/")
    def home() -> Any:
        if cfg.mode != "local":
            abort(404)
        token = session.get("demo_csrf")
        if not token:
            token = secrets.token_urlsafe(24)
            session["demo_csrf"] = token
        return render_template(
            "index.html", csrf_token=token, form_nonce=secrets.token_urlsafe(24), error=None, form={}
        )

    @app.post("/demo/submit")
    def demo_submit() -> Any:
        if cfg.mode != "local":
            abort(404)
        supplied = request.form.get("csrf_token", "")
        expected = session.get("demo_csrf", "")
        if (
            not supplied
            or not supplied.isascii()
            or not expected
            or not secrets.compare_digest(supplied, expected)
        ):
            return jsonify({"status": "error", "message": "Invalid demo form token. Refresh and retry."}), 403
        form_nonce = request.form.get("form_nonce", "")
        if not 24 <= len(form_nonce) <= 96 or not all(
            char.isascii() and (char.isalnum() or char in "-_") for char in form_nonce
        ):
            return jsonify(
                {"status": "error", "message": "Invalid submission token. Refresh and retry."}
            ), 403
        fields = (
            "brew_method",
            "roast_level",
            "caffeine_level",
            "milk_preference",
            "style_preference",
            "extra_notes",
        )
        submitted = {name: request.form.get(name) for name in fields}
        submitted["flavor_notes"] = request.form.getlist("flavor_notes")
        try:
            if set(request.form) - {"csrf_token", "form_nonce", *fields, "flavor_notes"} or any(
                len(request.form.getlist(name)) > 1 for name in (*fields, "csrf_token", "form_nonce")
            ):
                raise ValidationError("Unexpected or repeated form field.")
            preferences = normalize_preferences(submitted)
        except ValidationError as exc:
            return render_template(
                "index.html",
                csrf_token=expected,
                form_nonce=secrets.token_urlsafe(24),
                error=str(exc),
                form=submitted,
            ), 422
        response_id = secrets.token_urlsafe(18)
        recommendations = rank_recommendations(preferences, catalog)
        try:
            response_id = store.save_form_once(form_nonce, response_id, preferences, recommendations, digest)
        except ResponseConflict:
            return render_template(
                "index.html",
                csrf_token=expected,
                form_nonce=secrets.token_urlsafe(24),
                error="This form was already submitted with different preferences. Try submitting again.",
                form=submitted,
            ), 409
        # Preserve the session CSRF value for independently opened tabs.
        # Replaying one form nonce resolves to the same saved response.
        return redirect(url_for("results", response_id=response_id), code=303)

    @app.post("/typeform/webhook")
    def typeform_webhook() -> tuple[Any, int]:
        if not cfg.webhook_secret:
            return jsonify(
                {"status": "unavailable", "message": "Signed webhook integration is not configured."}
            ), 503
        raw = request.get_data(cache=True)
        if not verify_typeform_signature(raw, request.headers.get("Typeform-Signature"), cfg.webhook_secret):
            return jsonify({"status": "error", "message": "Invalid webhook signature."}), 401
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"status": "error", "message": "Malformed JSON body."}), 400
        try:
            response_id, preferences = normalize_typeform_payload(payload, cfg.form_id)
            recommendations = rank_recommendations(preferences, catalog)
            created = store.save_once(response_id, preferences, recommendations, digest)
        except ValidationError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 422
        except ResponseConflict:
            return jsonify({"status": "error", "message": "Response identifier conflict."}), 409
        app.logger.info("Accepted signed survey submission (new=%s)", created)
        return jsonify({"status": "success", "duplicate": not created, "response_id": response_id}), 200

    @app.get("/api/recommendations/<response_id>")
    def recommendation_api(response_id: str) -> tuple[Any, int]:
        try:
            response_id = validate_response_id(response_id)
        except ValidationError:
            return jsonify({"status": "error", "message": "Invalid response identifier."}), 400
        record = store.get(response_id)
        if record is None:
            return jsonify({"status": "not_found", "message": "No recommendations found."}), 404
        return jsonify(record), 200

    @app.get("/api/recommendations/preview")
    def preview_get_not_allowed() -> tuple[Any, int]:
        if cfg.mode != "local":
            abort(404)
        return jsonify({"status": "error", "message": "Use POST for a recommendation preview."}), 405

    @app.route("/api/recommendations/preview", methods=["POST", "OPTIONS"])
    def preview() -> tuple[Any, int]:
        if cfg.mode != "local":
            abort(404)
        if request.method == "OPTIONS":
            return jsonify({}), 204
        body = request.get_json(silent=True)
        try:
            prefs = normalize_preferences(body)
        except ValidationError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 422
        return jsonify(
            {
                "status": "preview",
                "preferences": prefs.public_dict(),
                "catalog_digest": digest,
                "algorithm_version": ALGORITHM_VERSION,
                "recommendations": rank_recommendations(prefs, catalog),
                "cart_preview_only": True,
            }
        ), 200

    @app.get("/results/<response_id>")
    def results(response_id: str) -> Any:
        try:
            response_id = validate_response_id(response_id)
        except ValidationError:
            abort(404)
        record = store.get(response_id)
        if record is None:
            abort(404)
        return render_template(
            "results.html", result=record, add_all_url=cart_preview_url(record["recommendations"])
        )
