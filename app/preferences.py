"""Strictly normalize local form data and Typeform answer payloads.

Only structured, validated choices affect recommendations. Optional free text is
neither scored nor persisted; no attempt is made to infer sentiment from prose.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

RESPONSE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$", re.ASCII)
STYLE_OPTIONS = ("bright", "balanced", "bold")
OPTIONS = {
    "brew_method": ("pour-over", "drip", "espresso", "french press", "cold brew", "more than one"),
    "flavor_notes": (
        "fruity",
        "floral",
        "chocolatey",
        "nutty",
        "earthy",
        "spicy",
        "caramel",
        "citrus",
        "berry",
    ),
    "roast_level": ("light", "medium", "dark"),
    "caffeine_level": ("regular", "high-caffeine", "decaf"),
    "milk_preference": ("black", "dairy", "non-dairy", "other"),
}
VOCABULARY = {**OPTIONS, "style_preference": STYLE_OPTIONS}
ALLOWED_TYPEFORM_FIELDS = frozenset({*VOCABULARY, "extra_notes"})
ALIASES = {
    "pour over": "pour-over",
    "pourover": "pour-over",
    "filter": "drip",
    "french-press": "french press",
    "cold-brew": "cold brew",
    "multiple": "more than one",
    "many": "more than one",
    "fruit": "fruity",
    "chocolate": "chocolatey",
    "nut": "nutty",
    "high caffeine": "high-caffeine",
    "high": "high-caffeine",
    "non dairy": "non-dairy",
    "nondairy": "non-dairy",
    "with milk": "dairy",
    "no milk": "black",
    "decaffeinated": "decaf",
}


class ValidationError(ValueError):
    """Public-safe error raised for invalid untrusted input."""


@dataclass(frozen=True)
class Preferences:
    brew_method: str | None
    flavor_notes: tuple[str, ...]
    roast_level: str | None
    caffeine_level: str | None
    milk_preference: str | None
    style_preference: str | None = None
    extra_notes: str | None = None

    def public_dict(self) -> dict[str, Any]:
        """Return every scoring input, excluding optional free text/possible PII."""
        return {
            "brew_method": self.brew_method,
            "flavor_notes": list(self.flavor_notes),
            "roast_level": self.roast_level,
            "caffeine_level": self.caffeine_level,
            "milk_preference": self.milk_preference,
            "style_preference": self.style_preference,
        }


def validate_response_id(value: Any) -> str:
    if not isinstance(value, str) or not RESPONSE_ID_PATTERN.fullmatch(value):
        raise ValidationError("Invalid response identifier.")
    return value


def _choice(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 80:
        raise ValidationError(f"Invalid {field} value.")
    item = " ".join(value.strip().casefold().split())
    item = ALIASES.get(item, item)
    if item not in VOCABULARY[field]:
        raise ValidationError(f"Unsupported {field} value.")
    return item


def _flavors(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if not isinstance(value, (list, tuple)) or len(value) > 9:
        raise ValidationError("Flavor notes must be a short list.")
    found: list[str] = []
    for entry in value:
        item = _choice(entry, "flavor_notes")
        if item and item not in found:
            found.append(item)
    return tuple(found)


def normalize_preferences(data: Any) -> Preferences:
    if not isinstance(data, dict):
        raise ValidationError("Preferences must be a JSON object.")
    allowed = {*VOCABULARY, "extra_notes"}
    if set(data) - allowed:
        raise ValidationError("Unrecognized preference field.")
    notes = data.get("extra_notes")
    if notes is not None:
        if (
            not isinstance(notes, str)
            or len(notes) > 200
            or any(ord(c) < 32 and c not in "\t\n" or 0xD800 <= ord(c) <= 0xDFFF for c in notes)
        ):
            raise ValidationError("Notes must be text of at most 200 characters.")
        notes = notes.strip() or None
    prefs = Preferences(
        brew_method=_choice(data.get("brew_method"), "brew_method"),
        flavor_notes=_flavors(data.get("flavor_notes", [])),
        roast_level=_choice(data.get("roast_level"), "roast_level"),
        caffeine_level=_choice(data.get("caffeine_level"), "caffeine_level"),
        milk_preference=_choice(data.get("milk_preference"), "milk_preference"),
        style_preference=_choice(data.get("style_preference"), "style_preference"),
        extra_notes=notes,
    )
    if not any(
        (
            prefs.brew_method,
            prefs.flavor_notes,
            prefs.roast_level,
            prefs.caffeine_level,
            prefs.milk_preference,
            prefs.style_preference,
        )
    ):
        raise ValidationError("Choose at least one structured coffee preference.")
    return prefs


def _typeform_answer_value(answer: dict[str, Any]) -> Any:
    kind = answer.get("type")
    if kind == "choice":
        choice = answer.get("choice")
        if not isinstance(choice, dict):
            raise ValidationError("Malformed choice answer.")
        return choice.get("label")
    if kind == "choices":
        choices = answer.get("choices")
        if not isinstance(choices, dict):
            raise ValidationError("Malformed multiple-choice answer.")
        return choices.get("labels")
    if kind == "text":
        return answer.get("text")
    raise ValidationError("Unsupported Typeform answer type for a preference field.")


def normalize_typeform_payload(payload: Any, expected_form_id: str | None = None) -> tuple[str, Preferences]:
    if not isinstance(payload, dict):
        raise ValidationError("Webhook must be a JSON object.")
    if payload.get("event_type") != "form_response":
        raise ValidationError("Unexpected webhook event type.")
    response = payload.get("form_response")
    if not isinstance(response, dict):
        raise ValidationError("Missing form_response object.")
    if expected_form_id and response.get("form_id") != expected_form_id:
        raise ValidationError("Unexpected form identifier.")
    response_id = validate_response_id(response.get("token"))
    answers = response.get("answers")
    if not isinstance(answers, list) or len(answers) > 100:
        raise ValidationError("Invalid Typeform answers array.")
    data: dict[str, Any] = {}
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValidationError("Malformed Typeform answer.")
        field = answer.get("field")
        # Unknown fields, including those containing contact data, are ignored.
        ref = field.get("ref") if isinstance(field, dict) else None
        if isinstance(ref, str) and ref in ALLOWED_TYPEFORM_FIELDS:
            if ref in data:
                raise ValidationError("Duplicate Typeform field reference.")
            data[ref] = _typeform_answer_value(answer)
    return response_id, normalize_preferences(data)
