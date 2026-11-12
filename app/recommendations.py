"""Traceable and deterministic coffee scoring with strict caffeine eligibility."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .preferences import Preferences

ALGORITHM_VERSION = "weighted-v2"
WEIGHTS = {
    "roast_level": 5,
    "brew_method": 4,
    "caffeine_level": 3,
    "milk_preference": 2,
    "flavor_note": 3,
    "style_preference": 2,
}


def score_product(product: dict[str, Any], prefs: Preferences) -> tuple[int, dict[str, int], list[str]]:
    traits = product["traits"]
    breakdown: dict[str, int] = {}
    reasons: list[str] = []
    for key in ("roast_level", "brew_method", "caffeine_level", "milk_preference"):
        choice = getattr(prefs, key)
        if choice and choice in traits[key]:
            breakdown[key] = WEIGHTS[key]
            explanations = {
                "roast_level": f"your {choice} roast preference",
                "brew_method": f"your {choice} brewing method",
                "caffeine_level": f"your {choice} caffeine preference",
                "milk_preference": f"your {choice} milk preference",
            }
            reasons.append(explanations[key])
    matches = sorted(set(prefs.flavor_notes).intersection(traits["flavor_notes"]))
    if matches:
        breakdown["flavor_notes"] = len(matches) * WEIGHTS["flavor_note"]
        reasons.append("flavors you enjoy: " + ", ".join(matches))
    # This is an explicit survey choice, NOT sentiment inferred from private notes.
    if prefs.style_preference and product["style"] == prefs.style_preference:
        breakdown["style_preference"] = WEIGHTS["style_preference"]
        reasons.append(f"your chosen {prefs.style_preference} coffee style")
    return sum(breakdown.values()), breakdown, reasons


def cart_preview_url(products: list[dict[str, Any]], *, store_base: str = "https://shop.example") -> str:
    """Illustrative Shopify cart permalink, not a working store integration."""
    variant_items = ",".join(f"{p['variant_id']}:1" for p in products)
    return f"{store_base}/cart/{variant_items}?storefront=true"


def product_preview_url(product: dict[str, Any], *, store_base: str = "https://shop.example") -> str:
    return f"{store_base}/products/{quote(product['handle'], safe='')}"


def rank_recommendations(prefs: Preferences, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluated = []
    for product in catalog:
        if not product["active"]:
            continue
        # A caffeine choice is a compatibility requirement, not a small ranking bonus.
        if prefs.caffeine_level and prefs.caffeine_level not in product["traits"]["caffeine_level"]:
            continue
        score, breakdown, reasons = score_product(product, prefs)
        evaluated.append((score, product["title"].casefold(), product["key"], product, breakdown, reasons))
    if len(evaluated) < 3:
        raise ValueError("At least three caffeine-compatible active products are required.")
    evaluated.sort(key=lambda entry: (-entry[0], entry[1], entry[2]))
    selected = []
    for position, (score, _, _, product, breakdown, reasons) in enumerate(evaluated[:3], 1):
        description = (
            ("Selected for " + "; ".join(reasons) + ".")
            if reasons
            else ("An exploratory alternative; none of your selected preferences match this product.")
        )
        selected.append(
            {
                "rank": position,
                "product_key": product["key"],
                "title": product["title"],
                "handle": product["handle"],
                "price": product["price"],
                "variant_id": product["variant_id"],
                "palette": product["palette"],
                "style": product["style"],
                "score": score,
                "match_quality": "matched" if score else "exploratory",
                "score_breakdown": breakdown,
                "why": description,
                "cart_preview_url": cart_preview_url([product]),
                "product_preview_url": product_preview_url(product),
            }
        )
    return selected
