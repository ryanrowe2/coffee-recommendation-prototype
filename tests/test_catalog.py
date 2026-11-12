from copy import deepcopy
import pytest

from app.catalog import CatalogError, load_catalog, validate_catalog


def test_catalog_has_synthetic_products(catalog):
    assert len(catalog) == 9
    assert len([x for x in catalog if x["active"]]) == 8
    assert all(x["variant_id"].startswith("9900000") for x in catalog)


@pytest.mark.parametrize(
    "change",
    [
        lambda a: a[0].update(key="../bad"),
        lambda a: a[1].update(key=a[0]["key"]),
        lambda a: a[0].update(price="free"),
        lambda a: a[0].update(variant_id="../../etc"),
        lambda a: a[1].update(variant_id=a[0]["variant_id"]),
        lambda a: a[0].update(active="yes"),
        lambda a: a[0].update(availability_type="forever"),
        lambda a: a[0].update(palette="transparent"),
        lambda a: a[0]["traits"].update(roast_level=["extra-dark"]),
        lambda a: a[0]["traits"].update(flavor_notes=["fruity", "fruity"]),
        lambda a: a[0].update(title="X"),
        lambda a: a[0].update(handle="https://unsafe"),
        lambda a: a[1].update(handle=a[0]["handle"]),
        lambda a: a[0].update(title="  padded title"),
        lambda a: a[0].update(title="New\nline"),
        lambda a: a[0].update(title="Broken\ud800"),
        lambda a: a[0].update(title="Invisible\u200bText"),
        lambda a: a[0].update(style="unknown"),
    ],
)
def test_invalid_catalog_fields_rejected(catalog, change):
    data = deepcopy(catalog)
    change(data)
    with pytest.raises(CatalogError):
        validate_catalog(data)


def test_too_few_active_fails(catalog):
    data = deepcopy(catalog)
    for product in data[1:]:
        product["active"] = False
    with pytest.raises(CatalogError, match="active"):
        validate_catalog(data)


def test_missing_file_fails(tmp_path):
    with pytest.raises(CatalogError):
        load_catalog(tmp_path / "missing.json")


def test_invalid_json_fails(tmp_path):
    p = tmp_path / "catalog.json"
    p.write_text("bad json")
    with pytest.raises(CatalogError):
        load_catalog(p)
