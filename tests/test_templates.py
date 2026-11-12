"""Test Jinja rendering and escaping even when Flask is unavailable offline."""

from copy import deepcopy

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import ROOT
from app.preferences import normalize_preferences
from app.recommendations import cart_preview_url, rank_recommendations


def environment():
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.globals["url_for"] = lambda endpoint, filename: "/static/" + filename
    return env


def test_landing_template_renders_csrf_input():
    html = (
        environment()
        .get_template("index.html")
        .render(csrf_token="example-csrf", form_nonce="example-nonce", error=None, form={})
    )
    assert 'name="csrf_token" value="example-csrf"' in html
    assert 'name="form_nonce" value="example-nonce"' in html
    assert 'name="flavor_notes"' in html
    assert 'name="extra_notes"' in html


def test_results_template_three_ranked_cards_and_api_link(catalog):
    prefs = normalize_preferences({"roast_level": "light", "brew_method": "pour-over"})
    results = rank_recommendations(prefs, catalog)
    html = (
        environment()
        .get_template("results.html")
        .render(
            result={
                "response_id": "example0001",
                "preferences": prefs.public_dict(),
                "recommendations": results,
            },
            add_all_url=cart_preview_url(results),
        )
    )
    assert html.count('class="product-card"') == 3
    assert 'href="/api/recommendations/example0001"' in html
    assert "Sunbeam Citrus" in html
    assert "These are fictional coffees" in html


def test_product_data_escaped_in_result(catalog):
    prefs = normalize_preferences({"roast_level": "light"})
    results = rank_recommendations(prefs, catalog)
    injection = '<img src=x onerror="alert(1)">'
    hacked = deepcopy(results)
    hacked[0]["title"] = injection
    html = (
        environment()
        .get_template("results.html")
        .render(
            result={
                "response_id": "example0001",
                "preferences": prefs.public_dict(),
                "recommendations": hacked,
            },
            add_all_url=cart_preview_url(hacked),
        )
    )
    assert injection not in html
    assert "&lt;img" in html
