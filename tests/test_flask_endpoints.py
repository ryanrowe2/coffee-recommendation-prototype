"""Executed by CI with Flask installed. Skipped explicitly in limited offline runtimes."""

import base64
import hashlib
import hmac
import json
import re
from copy import deepcopy

import pytest

from app import create_app

pytest.importorskip("flask", reason="Flask runtime dependency unavailable in this environment")


@pytest.fixture
def client(local_config):
    app = create_app(local_config)
    app.config.update(TESTING=True)
    return app.test_client()


def _hidden(page, name: str) -> str:
    match = re.search(rb'name="' + name.encode() + rb'" value="([^"]+)"', page.data)
    assert match is not None, f"Missing hidden {name} input"
    return match.group(1).decode()


def signed_headers(payload: dict, secret: str = "this-is-a-local-test-secret-123456"):
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    return body, {"Content-Type": "application/json", "Typeform-Signature": "sha256=" + sig}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json["status"] == "ok" and "secret" not in str(r.json)


def test_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200 and b"perfect cup" in r.data
    assert b"csrf_token" in r.data and b"form_nonce" in r.data and b"COFFEE ATLAS" in r.data


def test_end_to_end_form_to_results_and_api(client):
    page = client.get("/")
    token = _hidden(page, "csrf_token")
    nonce = _hidden(page, "form_nonce")
    post = client.post(
        "/demo/submit",
        data={
            "csrf_token": token,
            "form_nonce": nonce,
            "brew_method": "pour-over",
            "roast_level": "light",
            "flavor_notes": ["citrus", "fruity"],
            "caffeine_level": "regular",
            "milk_preference": "black",
        },
    )
    assert post.status_code == 303
    uri = post.headers["Location"]
    html = client.get(uri)
    assert html.status_code == 200 and b"Sunbeam Citrus" in html.data
    assert html.data.count(b'class="product-card"') == 3
    assert b"example cart URL" in html.data
    rid = uri.split("/")[-1]
    api = client.get(f"/api/recommendations/{rid}")
    assert api.status_code == 200 and len(api.json["recommendations"]) == 3
    assert api.json["preferences"]["roast_level"] == "light"
    assert api.json["recommendations"][0]["score"] > 0


def test_csrf_prevents_unsolicited_form(client):
    assert client.post("/demo/submit", data={"roast_level": "light"}).status_code == 403


def test_invalid_form_value(client):
    p = client.get("/")
    token = _hidden(p, "csrf_token")
    nonce = _hidden(p, "form_nonce")
    r = client.post(
        "/demo/submit", data={"csrf_token": token, "form_nonce": nonce, "roast_level": "superlight"}
    )
    assert r.status_code == 422 and b"Unsupported roast_level" in r.data


def test_unsigned_webhook_rejected(client, example_payload):
    r = client.post("/typeform/webhook", json=example_payload)
    assert r.status_code == 401


def test_signed_webhook_idempotent(client, example_payload):
    body, headers = signed_headers(example_payload)
    first = client.post("/typeform/webhook", data=body, headers=headers)
    assert first.status_code == 200 and first.json["duplicate"] is False
    second = client.post("/typeform/webhook", data=body, headers=headers)
    assert second.status_code == 200 and second.json["duplicate"] is True
    assert client.get("/results/sample-response-001").status_code == 200


def test_webhook_signature_tampering(client, example_payload):
    body, headers = signed_headers(example_payload)
    changed = body.replace(b"Pour-over", b"Espresso")
    assert client.post("/typeform/webhook", data=changed, headers=headers).status_code == 401


def test_conflicting_submission(client, example_payload):
    body, hdr = signed_headers(example_payload)
    assert client.post("/typeform/webhook", data=body, headers=hdr).status_code == 200
    altered = deepcopy(example_payload)
    altered["form_response"]["answers"][1]["choice"]["label"] = "Dark"
    body2, hdr2 = signed_headers(altered)
    assert client.post("/typeform/webhook", data=body2, headers=hdr2).status_code == 409


def test_bad_typeform_format(client, example_payload):
    example_payload["form_response"]["token"] = "../secret"
    body, hdr = signed_headers(example_payload)
    r = client.post("/typeform/webhook", data=body, headers=hdr)
    assert r.status_code == 422


def test_wrong_form_id(client, example_payload):
    example_payload["form_response"]["form_id"] = "wrong"
    body, hdr = signed_headers(example_payload)
    assert client.post("/typeform/webhook", data=body, headers=hdr).status_code == 422


def test_preview_returns_three_and_does_not_store(client):
    r = client.post("/api/recommendations/preview", json={"roast_level": "dark", "flavor_notes": ["spicy"]})
    assert r.status_code == 200 and len(r.json["recommendations"]) == 3
    assert [p["product_key"] for p in r.json["recommendations"][:2]] == ["bold_midnight", "bold_nightfall"]
    assert [p["score"] for p in r.json["recommendations"][:2]] == [8, 8]
    assert client.get("/api/recommendations/preview").status_code == 405


def test_preview_bad_json_and_fields(client):
    assert (
        client.post("/api/recommendations/preview", data="oops", content_type="application/json").status_code
        == 422
    )
    assert client.post("/api/recommendations/preview", json={"roast_level": "invalid"}).status_code == 422


def test_invalid_and_missing_response_ids(client):
    assert client.get("/api/recommendations/../bad").status_code == 404
    assert client.get("/api/recommendations/a!").status_code == 400
    assert client.get("/api/recommendations/missing0000").status_code == 404
    assert client.get("/results/missing0000").status_code == 404


def test_debug_endpoints_not_available(client):
    assert client.get("/debug/latest").status_code == 404
    assert client.get("/debug/response/missing0000").status_code == 404


def test_large_request_blocked(client):
    r = client.post("/api/recommendations/preview", data=b"a" * 66000, content_type="application/json")
    assert r.status_code == 413


def test_csp_cors_safe_defaults(client):
    r = client.get("/health", headers={"Origin": "https://malicious.example"})
    assert "Access-Control-Allow-Origin" not in r.headers
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_html_escaping_recommendation_content(client, local_config, catalog):
    # All user-facing fields come from a constrained catalog and validated vocabulary.
    r = client.post(
        "/api/recommendations/preview",
        json={"roast_level": "light", "extra_notes": "<img src=x onerror=alert(1)>"},
    )
    assert r.status_code == 200 and "<img" not in r.get_data(as_text=True)


def test_production_disables_local_demo(local_config):
    from dataclasses import replace

    app = create_app(replace(local_config, mode="production"))
    client = app.test_client()
    assert client.get("/").status_code == 404
    assert client.post("/demo/submit", data={}).status_code == 404
    assert client.post("/api/recommendations/preview", json={"roast_level": "dark"}).status_code == 404


def test_cors_explicit_allowlist(local_config):
    from dataclasses import replace

    app = create_app(replace(local_config, allowed_origins=("https://shop.example",)))
    c = app.test_client()
    r = c.get("/api/recommendations/not-found-001", headers={"Origin": "https://shop.example"})
    assert r.headers.get("Access-Control-Allow-Origin") == "https://shop.example"
    malicious = c.get("/api/recommendations/not-found-001", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in malicious.headers


def test_multitab_forms_share_csrf_without_invalidating(client):
    first = client.get("/")
    second = client.get("/")
    assert _hidden(first, "csrf_token") == _hidden(second, "csrf_token")
    assert _hidden(first, "form_nonce") != _hidden(second, "form_nonce")


def test_form_rejects_ambiguous_duplicate_fields(client):
    page = client.get("/")
    token = _hidden(page, "csrf_token")
    nonce = _hidden(page, "form_nonce")
    response = client.post(
        "/demo/submit", data={"csrf_token": token, "form_nonce": nonce, "roast_level": ["light", "dark"]}
    )
    assert response.status_code == 422
    assert b"repeated form field" in response.data


def test_form_rejects_unexpected_fields(client):
    page = client.get("/")
    token = _hidden(page, "csrf_token")
    nonce = _hidden(page, "form_nonce")
    response = client.post(
        "/demo/submit",
        data={"csrf_token": token, "form_nonce": nonce, "roast_level": "light", "tracking_key": "hidden"},
    )
    assert response.status_code == 422


def test_local_form_and_webhook_cache_not_stored(client):
    assert client.get("/").headers["Cache-Control"] == "no-store"
    assert client.post("/typeform/webhook", json={}).headers["Cache-Control"] == "no-store"


def test_payload_with_unrelated_typeform_answers(client, example_payload):
    example_payload["form_response"]["answers"].append(
        {"type": "email", "field": {"id": "not-known"}, "email": "someone@example.com"}
    )
    raw, headers = signed_headers(example_payload)
    assert client.post("/typeform/webhook", data=raw, headers=headers).status_code == 200
    record = client.get("/api/recommendations/sample-response-001")
    assert "someone@example.com" not in record.get_data(as_text=True)


def test_decaf_api_never_exposes_incompatible_products(client, catalog):
    response = client.post(
        "/api/recommendations/preview",
        json={
            "roast_level": "light",
            "brew_method": "pour-over",
            "flavor_notes": ["citrus", "fruity"],
            "caffeine_level": "decaf",
        },
    )
    assert response.status_code == 200
    lookup = {p["key"]: p for p in catalog}
    for item in response.json["recommendations"]:
        assert "decaf" in lookup[item["product_key"]]["traits"]["caffeine_level"]
    assert response.json["algorithm_version"] == "weighted-v2"
    assert len(response.json["catalog_digest"]) == 64


def test_notes_do_not_change_preview_scores(client):
    selection = {"roast_level": "light", "style_preference": "bright"}
    baseline = client.post("/api/recommendations/preview", json=selection)
    negated = client.post(
        "/api/recommendations/preview",
        json={
            **selection,
            "extra_notes": "I hate bright coffee",
        },
    )
    assert baseline.status_code == negated.status_code == 200
    assert baseline.json["recommendations"] == negated.json["recommendations"]
    assert "extra_notes" not in negated.json["preferences"]


def test_cors_normalizes_default_https_port(local_config):
    from dataclasses import replace

    app = create_app(replace(local_config, allowed_origins=("https://shop.example:443",)))
    client = app.test_client()
    response = client.get(
        "/api/recommendations/missing0001",
        headers={
            "Origin": "https://shop.example",
        },
    )
    assert response.headers["Access-Control-Allow-Origin"] == "https://shop.example"
    preflight = client.options(
        "/api/recommendations/missing0001",
        headers={
            "Origin": "https://shop.example:443",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.headers["Access-Control-Allow-Origin"] == "https://shop.example"
    assert "GET" in preflight.headers["Access-Control-Allow-Methods"]
    invalid = client.get("/api/recommendations/missing0001", headers={"Origin": "https://."})
    assert "Access-Control-Allow-Origin" not in invalid.headers


def test_local_form_duplicate_cookie_replays_same_result(local_config):
    app = create_app(local_config)
    first = app.test_client()
    second = app.test_client()
    html = first.get("/")
    token = _hidden(html, "csrf_token")
    nonce = _hidden(html, "form_nonce")
    # Simulate two concurrent requests carrying the same signed, pre-submission session cookie.
    cookie = first.get_cookie("session")
    assert cookie is not None
    second.set_cookie("session", cookie.value)
    inputs = {"csrf_token": token, "form_nonce": nonce, "caffeine_level": "decaf", "style_preference": "bold"}
    a = first.post("/demo/submit", data=inputs)
    b = second.post("/demo/submit", data=inputs)
    assert a.status_code == b.status_code == 303
    assert a.headers["Location"] == b.headers["Location"]
    rid = a.headers["Location"].split("/")[-1]
    record = first.get(f"/api/recommendations/{rid}")
    assert record.json["preferences"]["style_preference"] == "bold"
    assert record.json["catalog_digest"] == app.extensions["coffee_catalog_digest"]


def test_local_form_nonce_conflicting_answers_return_409(local_config):
    app = create_app(local_config)
    first = app.test_client()
    second = app.test_client()
    initial = first.get("/")
    token = _hidden(initial, "csrf_token")
    nonce = _hidden(initial, "form_nonce")
    second.set_cookie("session", first.get_cookie("session").value)
    a = first.post("/demo/submit", data={"csrf_token": token, "form_nonce": nonce, "roast_level": "light"})
    b = second.post("/demo/submit", data={"csrf_token": token, "form_nonce": nonce, "roast_level": "dark"})
    assert a.status_code == 303
    assert b.status_code == 409


def test_exploratory_product_labeled_in_html(client):
    initial = client.get("/")
    token = _hidden(initial, "csrf_token")
    nonce = _hidden(initial, "form_nonce")
    response = client.post(
        "/demo/submit", data={"csrf_token": token, "form_nonce": nonce, "milk_preference": "other"}
    )
    assert response.status_code == 303
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "EXPLORATORY" in html
    assert "none of your selected preferences match" in html


def test_multitab_submissions_create_distinct_results(client):
    tab_a = client.get("/")
    tab_b = client.get("/")
    assert _hidden(tab_a, "csrf_token") == _hidden(tab_b, "csrf_token")
    assert _hidden(tab_a, "form_nonce") != _hidden(tab_b, "form_nonce")
    first = client.post(
        "/demo/submit",
        data={
            "csrf_token": _hidden(tab_a, "csrf_token"),
            "form_nonce": _hidden(tab_a, "form_nonce"),
            "roast_level": "light",
        },
    )
    second = client.post(
        "/demo/submit",
        data={
            "csrf_token": _hidden(tab_b, "csrf_token"),
            "form_nonce": _hidden(tab_b, "form_nonce"),
            "roast_level": "dark",
        },
    )
    assert first.status_code == second.status_code == 303
    assert first.headers["Location"] != second.headers["Location"]
    assert client.get(first.headers["Location"]).status_code == 200
    assert client.get(second.headers["Location"]).status_code == 200


def test_missing_or_invalid_form_nonce_is_rejected(client):
    initial = client.get("/")
    csrf = _hidden(initial, "csrf_token")
    for nonce in ("", "?", "bad/nonce", "x" * 100):
        response = client.post(
            "/demo/submit",
            data={
                "csrf_token": csrf,
                "form_nonce": nonce,
                "roast_level": "light",
            },
        )
        assert response.status_code == 403


def test_json_provider_preserves_intended_key_order(client):
    assert client.application.json.sort_keys is False
    result = client.post("/api/recommendations/preview", json={"roast_level": "medium"})
    assert result.status_code == 200
    text = result.get_data(as_text=True)
    assert text.index('"status"') < text.index('"preferences"')


def test_unexpected_server_error_is_generic(client, monkeypatch):
    client.application.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)

    def fail(_):
        raise RuntimeError("private-survey-database-details")

    monkeypatch.setattr(client.application.extensions["coffee_store"], "get", fail)
    response = client.get("/api/recommendations/valid-response-id")
    assert response.status_code == 500
    assert response.json == {"status": "error", "message": "An internal error occurred."}
    assert b"private-survey" not in response.data


@pytest.mark.parametrize("token", ["café", "咖啡", "☕"])
def test_unicode_csrf_is_rejected_without_server_error(client, token):
    client.get("/")
    response = client.post(
        "/demo/submit", data={"csrf_token": token, "form_nonce": "x" * 32, "roast_level": "light"}
    )
    assert response.status_code == 403
    assert response.json["message"] == "Invalid demo form token. Refresh and retry."


def test_host_header_allowlist_blocks_untrusted_host(local_config):
    app = create_app(local_config)
    client = app.test_client()
    for host in ("evil.example", "127.0.0.1.evil.example", "bad.localhost.example"):
        assert client.get("/health", headers={"Host": host}).status_code == 400
        assert client.post("/api/recommendations/preview", headers={"Host": host}, json={}).status_code == 400
    for host in ("127.0.0.1", "localhost", "127.0.0.1:5050", "localhost:5050"):
        assert client.get("/health", headers={"Host": host}).status_code == 200


def test_session_cookie_survives_restart_for_open_form(local_config):
    app_before = create_app(local_config)
    browser = app_before.test_client()
    form = browser.get("/")
    csrf = _hidden(form, "csrf_token")
    nonce = _hidden(form, "form_nonce")
    cookie = browser.get_cookie("session")
    assert cookie is not None

    app_after = create_app(local_config)
    assert app_before.config["SECRET_KEY"] == app_after.config["SECRET_KEY"]
    resumed = app_after.test_client()
    resumed.set_cookie("session", cookie.value)
    response = resumed.post(
        "/demo/submit",
        data={"csrf_token": csrf, "form_nonce": nonce, "caffeine_level": "decaf"},
    )
    assert response.status_code == 303
    assert resumed.get(response.headers["Location"]).status_code == 200
