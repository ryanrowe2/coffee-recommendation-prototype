"""Load, validate and version the deliberately synthetic coffee catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .preferences import OPTIONS, STYLE_OPTIONS

KEY = re.compile(r"^[a-z][a-z0-9_-]{2,50}$")
HANDLE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PALETTES = {"gold", "sage", "cocoa", "berry", "slate", "terracotta"}


class CatalogError(ValueError):
    """Invalid catalog: fail application startup instead of producing bad results."""


def validate_catalog(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list) or not 3 <= len(data) <= 100:
        raise CatalogError("Catalog must have between 3 and 100 products.")
    keys: set[str] = set()
    variants: set[str] = set()
    handles: set[str] = set()
    results = []
    required = {
        "key",
        "title",
        "handle",
        "price",
        "variant_id",
        "active",
        "availability_type",
        "palette",
        "style",
        "traits",
    }
    for product in data:
        if not isinstance(product, dict) or set(product) != required:
            raise CatalogError("Product has missing or unexpected fields.")
        key = product["key"]
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in keys:
            raise CatalogError("Invalid or duplicate product key.")
        keys.add(key)
        title = product["title"]
        # isprintable rejects lone UTF-16 surrogates, bidi controls, and invisible
        # formatting characters that can break rendering or deceive reviewers.
        if (
            not isinstance(title, str)
            or not 3 <= len(title) <= 90
            or title != title.strip()
            or not title.isprintable()
        ):
            raise CatalogError("Invalid product title.")
        handle = product["handle"]
        if not isinstance(handle, str) or not HANDLE.fullmatch(handle) or handle in handles:
            raise CatalogError("Invalid or duplicate product handle.")
        handles.add(handle)
        price = product["price"]
        if not isinstance(price, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,4})\.[0-9]{2}", price):
            raise CatalogError("Invalid price.")
        variant = product["variant_id"]
        if (
            not isinstance(variant, str)
            or not re.fullmatch(r"[1-9][0-9]{9,19}", variant)
            or variant in variants
        ):
            raise CatalogError("Invalid or duplicate synthetic variant identifier.")
        variants.add(variant)
        if type(product["active"]) is not bool:
            raise CatalogError("Product active must be boolean.")
        if product["availability_type"] not in ("always", "monthly"):
            raise CatalogError("Invalid availability type.")
        if not isinstance(product["palette"], str) or product["palette"] not in PALETTES:
            raise CatalogError("Invalid palette.")
        if not isinstance(product["style"], str) or product["style"] not in STYLE_OPTIONS:
            raise CatalogError("Invalid style category.")
        traits = product["traits"]
        if not isinstance(traits, dict) or set(traits) != set(OPTIONS):
            raise CatalogError("Product trait categories must match the preference contract.")
        for field, allowed in OPTIONS.items():
            entries = traits[field]
            if not isinstance(entries, list) or not entries or len(entries) > len(allowed):
                raise CatalogError(f"Invalid trait list: {field}.")
            if any(not isinstance(item, str) or item not in allowed for item in entries) or len(
                set(entries)
            ) != len(entries):
                raise CatalogError(f"Unsupported or repeated catalog trait: {field}.")
        results.append(product)
    if sum(bool(p["active"]) for p in results) < 3:
        raise CatalogError("At least three products must be active.")
    # Exactly three results are promised for every selectable caffeine level.
    # Therefore each supported option needs a sufficient active pool.
    for caffeine in OPTIONS["caffeine_level"]:
        if sum(bool(p["active"]) and caffeine in p["traits"]["caffeine_level"] for p in results) < 3:
            raise CatalogError(f"At least three eligible active products are required for {caffeine}.")
    return results


def catalog_digest(data: list[dict[str, Any]]) -> str:
    """Content digest; independent of irrelevant JSON key/product ordering."""
    serialized = json.dumps(
        sorted(data, key=lambda p: p["key"]), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def load_catalog(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise CatalogError("Cannot read a valid JSON product catalog.") from exc
    return validate_catalog(data)
