from copy import deepcopy
import pytest

from app.preferences import (
    ValidationError,
    normalize_preferences,
    normalize_typeform_payload,
    validate_response_id,
)


def test_normalize_casing_and_aliases():
    p = normalize_preferences(
        {
            "brew_method": " POUR OVER ",
            "flavor_notes": ["FRUIT", "Citrus", "fruit"],
            "roast_level": "LIGHT",
            "milk_preference": "non dairy",
        }
    )
    assert p.brew_method == "pour-over" and p.flavor_notes == ("fruity", "citrus")
    assert p.milk_preference == "non-dairy"


def test_free_notes_not_public():
    p = normalize_preferences({"roast_level": "dark", "extra_notes": "secret@example.com"})
    assert "extra_notes" not in p.public_dict()
    assert "secret@example.com" not in str(p.public_dict())


@pytest.mark.parametrize(
    "value", [None, "", "../../path", "a/b", "ab", " badtoken!", "z" * 129, 123, ".hidden"]
)
def test_invalid_id(value):
    with pytest.raises(ValidationError):
        validate_response_id(value)


def test_valid_response_id():
    assert validate_response_id("abc-DEF_012345") == "abc-DEF_012345"


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"extra_notes": "only notes"},
        {"flavor_notes": "fruity"},
        {"roast_level": "ultra dark"},
        {"roast_level": 9},
        {"extra_notes": "x" * 201},
        {"extra_notes": "hi\x00"},
        {"extra_notes": ["a"]},
        {"unknown": "secret", "roast_level": "dark"},
    ],
)
def test_invalid_preference_data(data):
    with pytest.raises(ValidationError):
        normalize_preferences(data)


def test_input_validation_no_type_coercion():
    with pytest.raises(ValidationError):
        normalize_preferences({"flavor_notes": ["fruity", 3]})


def test_typeform_realistic_payload(example_payload):
    response_id, p = normalize_typeform_payload(example_payload, "DEMO_COFFEE_FORM")
    assert response_id == "sample-response-001"
    assert p.brew_method == "pour-over" and p.roast_level == "light"
    assert p.flavor_notes == ("fruity", "citrus", "floral")


def test_typeform_wrong_form_rejected(example_payload):
    with pytest.raises(ValidationError, match="form identifier"):
        normalize_typeform_payload(example_payload, "DIFFERENT")


def test_typeform_duplicate_field_rejected(example_payload):
    payload = deepcopy(example_payload)
    payload["form_response"]["answers"].append(payload["form_response"]["answers"][0])
    with pytest.raises(ValidationError, match="Duplicate"):
        normalize_typeform_payload(payload)


def test_typeform_ignores_unknown_fields(example_payload):
    payload = deepcopy(example_payload)
    payload["form_response"]["answers"].append(
        {"type": "email", "field": {"ref": "contact_email"}, "email": "example@example.com"}
    )
    _, p = normalize_typeform_payload(payload)
    assert "contact_email" not in str(p)


@pytest.mark.parametrize(
    "invalid",
    [
        {"form_response": []},
        {"form_response": {"token": "goodtoken00"}},
        {"form_response": {"token": "goodtoken00", "answers": [None]}},
    ],
)
def test_typeform_invalid_structure(invalid):
    with pytest.raises(ValidationError):
        normalize_typeform_payload(invalid)


def test_typeform_max_answer_count(example_payload):
    example_payload["form_response"]["answers"] = example_payload["form_response"]["answers"] * 25
    with pytest.raises(ValidationError):
        normalize_typeform_payload(example_payload)


def test_structured_style_is_scoring_input_and_notes_are_not():
    p = normalize_preferences({"style_preference": "BOLD", "extra_notes": "I hate bold coffee"})
    assert p.style_preference == "bold"
    assert p.public_dict()["style_preference"] == "bold"
    assert "hate" not in str(p.public_dict())


def test_typeform_ignores_unknown_fields_with_missing_or_malformed_refs(example_payload):
    payload = deepcopy(example_payload)
    payload["form_response"]["answers"].extend(
        [
            {"type": "email", "email": "private@example.com", "field": {"id": "ignored"}},
            {"type": "text", "text": "private", "field": {"ref": []}},
            {"type": "number", "number": 27},
        ]
    )
    rid, preferences = normalize_typeform_payload(payload, "DEMO_COFFEE_FORM")
    assert rid == "sample-response-001" and preferences.roast_level == "light"
    assert "private@example.com" not in str(preferences.public_dict())


def test_typeform_wrong_event_type_rejected(example_payload):
    example_payload["event_type"] = "payment"
    with pytest.raises(ValidationError, match="event type"):
        normalize_typeform_payload(example_payload)
