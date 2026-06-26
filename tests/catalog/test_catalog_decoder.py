from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog import Catalog
from mhwilds_skill_sim.catalog.decoder import (
    decode_catalog,
    decode_decoration_definition,
    decode_decoration_slot,
    decode_equipment_definition,
    decode_skill_contribution,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"


def load_tiny_catalog() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def equipment_value(
    equipment_id: str = "fixture:weapon:training-blade",
) -> dict[str, object]:
    return {
        "equipment_id": equipment_id,
        "part": "weapon",
        "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
        "slots": [{"kind": "weapon", "level": 1}],
    }


def alternate_equipment_value(
    equipment_id: str = "fixture:head:precision-alpha",
) -> dict[str, object]:
    return {
        "equipment_id": equipment_id,
        "part": "head",
        "skills": [{"skill_id": "skill:critical-eye", "level": 1}],
        "slots": [{"kind": "armor", "level": 1}],
    }


def decoration_value(
    decoration_id: str = "fixture:decoration:weapon-power-1",
) -> dict[str, object]:
    return {
        "decoration_id": decoration_id,
        "required_slot": {"kind": "weapon", "level": 1},
        "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
    }


def alternate_decoration_value(
    decoration_id: str = "fixture:decoration:armor-power-1",
) -> dict[str, object]:
    return {
        "decoration_id": decoration_id,
        "required_slot": {"kind": "armor", "level": 1},
        "skills": [{"skill_id": "skill:critical-eye", "level": 1}],
    }


def catalog_value() -> dict[str, object]:
    return {
        "schema_version": 1,
        "equipment": [equipment_value()],
        "decorations": [decoration_value()],
    }


def equipment_generator() -> Iterator[dict[str, object]]:
    yield equipment_value()


def decorations_generator() -> Iterator[dict[str, object]]:
    yield decoration_value()


def assert_nested_error_not_wrapped(error: CatalogDecodeError) -> None:
    assert not isinstance(error.__cause__, CatalogDecodeError)


def test_decode_catalog_converts_empty_catalog() -> None:
    catalog = decode_catalog(
        value={"schema_version": 1, "equipment": [], "decorations": []},
    )

    assert isinstance(catalog, Catalog)
    assert catalog.schema_version == 1
    assert catalog.equipment == ()
    assert catalog.decorations == ()


def test_decode_catalog_converts_tiny_catalog_fixture() -> None:
    catalog = decode_catalog(value=load_tiny_catalog())

    assert isinstance(catalog, Catalog)
    assert catalog.schema_version == 1
    assert len(catalog.equipment) == 9
    assert len(catalog.decorations) == 5


def test_decode_catalog_preserves_equipment_and_decoration_order() -> None:
    catalog = decode_catalog(value=load_tiny_catalog())

    assert [equipment.equipment_id for equipment in catalog.equipment] == [
        "fixture:weapon:training-blade",
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
        "fixture:chest:power-mail",
        "fixture:arms:socket-braces",
        "fixture:waist:precision-coil",
        "fixture:legs:tenderizer-greaves",
        "fixture:charm:power",
        "fixture:charm:precision",
    ]
    assert [decoration.decoration_id for decoration in catalog.decorations] == [
        "fixture:decoration:weapon-power-1",
        "fixture:decoration:weapon-precision-2",
        "fixture:decoration:armor-power-1",
        "fixture:decoration:armor-tenderizer-2",
        "fixture:decoration:armor-combination-2",
    ]


def test_decode_catalog_converts_tiny_catalog_nested_types() -> None:
    catalog = decode_catalog(value=load_tiny_catalog())

    assert {equipment.part for equipment in catalog.equipment} == {
        EquipmentPart.WEAPON,
        EquipmentPart.HEAD,
        EquipmentPart.CHEST,
        EquipmentPart.ARMS,
        EquipmentPart.WAIST,
        EquipmentPart.LEGS,
        EquipmentPart.CHARM,
    }
    assert isinstance(catalog.decorations[0].required_slot, DecorationSlot)
    assert all(type(equipment.skills) is tuple for equipment in catalog.equipment)
    assert all(type(equipment.slots) is tuple for equipment in catalog.equipment)
    assert all(type(decoration.skills) is tuple for decoration in catalog.decorations)


def test_decode_catalog_accepts_reverse_root_key_order() -> None:
    catalog = decode_catalog(
        value={
            "decorations": [decoration_value()],
            "equipment": [equipment_value()],
            "schema_version": 1,
        },
    )

    assert catalog.equipment[0].equipment_id == "fixture:weapon:training-blade"
    assert catalog.decorations[0].decoration_id == "fixture:decoration:weapon-power-1"


def test_decode_catalog_accepts_custom_path() -> None:
    catalog = decode_catalog(value=catalog_value(), path="$.catalog")

    assert catalog.schema_version == 1


def test_decode_catalog_does_not_mutate_nested_input() -> None:
    value = load_tiny_catalog()
    original = copy.deepcopy(value)

    decode_catalog(value=value)

    assert value == original


def test_decode_catalog_arguments_are_keyword_only() -> None:
    signature = inspect.signature(decode_catalog)

    assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        decode_catalog(catalog_value())  # type: ignore[call-arg]


def test_decode_catalog_accepts_large_schema_version() -> None:
    catalog = decode_catalog(
        value={"schema_version": 999, "equipment": [], "decorations": []},
    )

    assert catalog.schema_version == 999


def test_decode_catalog_accepts_shared_equipment_and_decoration_ids() -> None:
    shared_id = "shared:id"

    catalog = decode_catalog(
        value={
            "schema_version": 1,
            "equipment": [equipment_value(shared_id)],
            "decorations": [decoration_value(shared_id)],
        },
    )

    assert catalog.equipment[0].equipment_id == shared_id
    assert catalog.decorations[0].decoration_id == shared_id


@pytest.mark.parametrize("value", [None, "catalog", [], ()])
def test_decode_catalog_rejects_non_dict_objects(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "object" in exc_info.value.detail


def test_decode_catalog_rejects_dict_subclass() -> None:
    class CatalogDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=CatalogDict(catalog_value()), path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        ({"equipment": [], "decorations": []}, ("schema_version",)),
        ({"schema_version": 1, "decorations": []}, ("equipment",)),
        ({"schema_version": 1, "equipment": []}, ("decorations",)),
        ({}, ("schema_version", "equipment", "decorations")),
        (
            {
                "schema_version": 1,
                "equipment": [],
                "decorations": [],
                "extra": True,
            },
            ("extra",),
        ),
        (
            {
                "schema_version": 1,
                "equipment": [],
                "unexpected": True,
            },
            ("decorations", "unexpected"),
        ),
    ],
)
def test_decode_catalog_rejects_invalid_root_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    for expected_fragment in expected_fragments:
        assert expected_fragment in exc_info.value.detail


def test_decode_catalog_handles_non_string_extra_keys_deterministically() -> None:
    value = catalog_value()
    value[3] = True
    value[("x",)] = False

    with pytest.raises(CatalogDecodeError) as first_error:
        decode_catalog(value=value, path="$.catalog")
    with pytest.raises(CatalogDecodeError) as second_error:
        decode_catalog(value=value, path="$.catalog")

    assert first_error.value.path == "$.catalog"
    assert first_error.value.detail == second_error.value.detail
    assert "3" in first_error.value.detail
    assert "x" in first_error.value.detail


@pytest.mark.parametrize(
    ("schema_version", "expected_cause"),
    [
        (True, TypeError),
        (1.5, TypeError),
        ("1", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_decode_catalog_converts_invalid_schema_version_errors(
    schema_version: object,
    expected_cause: type[Exception],
) -> None:
    value = catalog_value()
    value["schema_version"] = schema_version

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.schema_version"
    assert "schema_version" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    "equipment",
    [
        (equipment_value(),),
        {"equipment_id": "fixture:weapon:training-blade"},
        {("fixture:weapon:training-blade", "weapon")},
        equipment_generator(),
        None,
    ],
)
def test_decode_catalog_rejects_non_list_equipment(equipment: object) -> None:
    value = catalog_value()
    value["equipment"] = equipment

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.equipment"
    assert "equipment" in exc_info.value.detail


def test_decode_catalog_rejects_equipment_list_subclass() -> None:
    class EquipmentList(list[object]):
        pass

    value = catalog_value()
    value["equipment"] = EquipmentList([equipment_value()])

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.equipment"
    assert "equipment" in exc_info.value.detail


@pytest.mark.parametrize(
    ("equipment", "expected_path"),
    [
        ([{"part": "weapon", "skills": [], "slots": []}], "$.catalog.equipment[0]"),
        (
            [equipment_value(), {"part": "head", "skills": [], "slots": []}],
            "$.catalog.equipment[1]",
        ),
        (
            [dict(equipment_value(), part="body")],
            "$.catalog.equipment[0].part",
        ),
    ],
)
def test_decode_catalog_propagates_equipment_element_errors(
    equipment: list[object],
    expected_path: str,
) -> None:
    value = catalog_value()
    value["equipment"] = equipment

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == expected_path
    assert_nested_error_not_wrapped(exc_info.value)


@pytest.mark.parametrize(
    "decorations",
    [
        (decoration_value(),),
        {"decoration_id": "fixture:decoration:weapon-power-1"},
        {("fixture:decoration:weapon-power-1", "weapon")},
        decorations_generator(),
        None,
    ],
)
def test_decode_catalog_rejects_non_list_decorations(decorations: object) -> None:
    value = catalog_value()
    value["decorations"] = decorations

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.decorations"
    assert "decorations" in exc_info.value.detail


def test_decode_catalog_rejects_decorations_list_subclass() -> None:
    class DecorationList(list[object]):
        pass

    value = catalog_value()
    value["decorations"] = DecorationList([decoration_value()])

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.decorations"
    assert "decorations" in exc_info.value.detail


@pytest.mark.parametrize(
    ("decorations", "expected_path"),
    [
        (
            [{"required_slot": {"kind": "weapon", "level": 1}, "skills": []}],
            "$.catalog.decorations[0]",
        ),
        (
            [
                decoration_value(),
                {"required_slot": {"kind": "armor", "level": 1}, "skills": []},
            ],
            "$.catalog.decorations[1]",
        ),
        (
            [dict(decoration_value(), required_slot={"kind": "body", "level": 1})],
            "$.catalog.decorations[0].required_slot",
        ),
    ],
)
def test_decode_catalog_propagates_decoration_element_errors(
    decorations: list[object],
    expected_path: str,
) -> None:
    value = catalog_value()
    value["decorations"] = decorations

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == expected_path
    assert_nested_error_not_wrapped(exc_info.value)


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_value(), equipment_value()],
        [equipment_value(), alternate_equipment_value("fixture:weapon:training-blade")],
    ],
)
def test_decode_catalog_converts_duplicate_equipment_id_errors(
    equipment: list[dict[str, object]],
) -> None:
    value = catalog_value()
    value["equipment"] = equipment

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "equipment" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "decorations",
    [
        [decoration_value(), decoration_value()],
        [
            decoration_value(),
            alternate_decoration_value("fixture:decoration:weapon-power-1"),
        ],
    ],
)
def test_decode_catalog_converts_duplicate_decoration_id_errors(
    decorations: list[dict[str, object]],
) -> None:
    value = catalog_value()
    value["decorations"] = decorations

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "decorations" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_existing_skill_contribution_decoder_still_works() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "skill:attack-boost", "level": 1},
    )

    assert contribution == SkillContribution("skill:attack-boost", 1)


def test_existing_decoration_slot_decoder_still_works() -> None:
    slot = decode_decoration_slot(value={"kind": "weapon", "level": 1})

    assert slot == DecorationSlot(DecorationKind.WEAPON, 1)


def test_existing_decoration_definition_decoder_still_works() -> None:
    decoration = decode_decoration_definition(value=decoration_value())

    assert decoration == DecorationDefinition(
        decoration_id="fixture:decoration:weapon-power-1",
        required_slot=DecorationSlot(DecorationKind.WEAPON, 1),
        skills=(SkillContribution("skill:attack-boost", 1),),
    )


def test_existing_equipment_definition_decoder_still_works() -> None:
    equipment = decode_equipment_definition(value=equipment_value())

    assert equipment == EquipmentDefinition(
        equipment_id="fixture:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(SkillContribution("skill:attack-boost", 1),),
        slots=(DecorationSlot(DecorationKind.WEAPON, 1),),
    )


def test_catalog_decode_error_still_imports_directly() -> None:
    error = CatalogDecodeError(path="$.catalog", detail="invalid object")

    assert str(error) == "$.catalog: invalid object"
