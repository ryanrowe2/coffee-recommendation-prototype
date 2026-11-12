from copy import deepcopy
import pytest

from app.preferences import normalize_preferences
from app.recommendations import WEIGHTS, cart_preview_url, rank_recommendations, score_product


def test_weights_preserve_original_algorithm():
    assert WEIGHTS == {
        "roast_level": 5,
        "brew_method": 4,
        "caffeine_level": 3,
        "milk_preference": 2,
        "flavor_note": 3,
        "style_preference": 2,
    }


def test_top_match_is_bright(catalog):
    prefs = normalize_preferences(
        {
            "roast_level": "light",
            "brew_method": "pour-over",
            "flavor_notes": ["citrus", "fruity"],
            "caffeine_level": "regular",
        }
    )
    results = rank_recommendations(prefs, catalog)
    assert results[0]["product_key"] == "bright_sunbeam"
    assert results[0]["score"] == 18
    assert results[0]["score_breakdown"] == {
        "roast_level": 5,
        "brew_method": 4,
        "flavor_notes": 6,
        "caffeine_level": 3,
    }
    assert "citrus" in results[0]["why"]
    assert [p["rank"] for p in results] == [1, 2, 3]


def test_dark_espresso(catalog):
    prefs = normalize_preferences(
        {
            "roast_level": "dark",
            "brew_method": "espresso",
            "flavor_notes": ["spicy"],
            "caffeine_level": "regular",
        }
    )
    assert rank_recommendations(prefs, catalog)[0]["product_key"] == "bold_nightfall"


def test_decaf(catalog):
    prefs = normalize_preferences({"caffeine_level": "decaf"})
    assert rank_recommendations(prefs, catalog)[0]["product_key"] == "balanced_decaf"


def test_deterministic(catalog):
    p = normalize_preferences({"roast_level": "medium", "flavor_notes": ["chocolatey", "nutty"]})
    assert rank_recommendations(p, catalog) == rank_recommendations(p, catalog)


def test_ties_sorted_by_title_and_key(catalog):
    p = normalize_preferences({"milk_preference": "other"})
    data = deepcopy(catalog)
    for product in data:
        product["traits"]["milk_preference"] = ["other"]
    results = rank_recommendations(p, data)
    titles = [r["title"] for r in results]
    assert titles == sorted(titles, key=str.casefold)


def test_inactive_never_ranked(catalog):
    p = normalize_preferences({"roast_level": "dark"})
    assert "bold_seasonal" not in {r["product_key"] for r in rank_recommendations(p, catalog)}


def test_all_active_or_monthly_both_possible(catalog):
    p = normalize_preferences({"flavor_notes": ["berry"]})
    assert rank_recommendations(p, catalog)[0]["product_key"] == "bright_orchard"


def test_exploratory_candidates_are_labeled(catalog):
    p = normalize_preferences({"milk_preference": "other"})
    results = rank_recommendations(p, catalog)
    assert any(r["score"] == 0 for r in results)
    for item in results:
        if item["score"] == 0:
            assert item["match_quality"] == "exploratory"
            assert "none of your selected preferences match" in item["why"]


def test_explicit_style_preference_is_scored(catalog):
    p = normalize_preferences({"style_preference": "bold"})
    bold = next(x for x in catalog if x["key"] == "bold_nightfall")
    assert score_product(bold, p)[0] == 2


def test_no_raw_note_in_explanation(catalog):
    p = normalize_preferences({"roast_level": "light", "extra_notes": "myprivatecode123"})
    assert "myprivatecode" not in str(rank_recommendations(p, catalog))


def test_catalog_order_does_not_change_rank(catalog):
    p = normalize_preferences({"brew_method": "drip"})
    assert rank_recommendations(p, catalog) == rank_recommendations(p, list(reversed(catalog)))


def test_exactly_three_or_fail(catalog):
    p = normalize_preferences({"roast_level": "light"})
    small = deepcopy(catalog)
    for product in small[2:]:
        product["active"] = False
    with pytest.raises(ValueError, match="three"):
        rank_recommendations(p, small)


def test_cart_permalink_is_synthetic_and_structural(catalog):
    url = cart_preview_url(catalog[:2])
    assert url == "https://shop.example/cart/99000000000001:1,99000000000002:1?storefront=true"


def test_explanations_contain_only_selected_matches(catalog):
    p = normalize_preferences({"flavor_notes": ["citrus"]})
    for result in rank_recommendations(p, catalog):
        if result["score"]:
            assert "citrus" in result["why"]


def test_copy_url_never_points_at_a_real_store(catalog):
    urls = [
        cart_preview_url(catalog[:3]),
        *[
            item["cart_preview_url"]
            for item in rank_recommendations(normalize_preferences({"brew_method": "drip"}), catalog)
        ],
    ]
    assert all(url.startswith("https://shop.example/") for url in urls)


def test_negative_free_text_is_not_scored(catalog):
    p = normalize_preferences({"roast_level": "dark", "extra_notes": "I hate bold coffee"})
    bold = next(x for x in catalog if x["key"] == "bold_nightfall")
    assert score_product(bold, p)[1] == {"roast_level": 5}
