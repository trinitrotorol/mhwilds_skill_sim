from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog import Catalog
from mhwilds_skill_sim.catalog.decoder import (
    decode_appraisal_charm_pattern_definition,
    decode_appraisal_charm_skill_group_definition,
    decode_catalog,
    decode_decoration_definition,
    decode_decoration_slot,
    decode_equipment_definition,
    decode_skill_contribution,
    decode_skill_definition,
    decode_skill_rank_definition,
)
from mhwilds_skill_sim.catalog.errors import CatalogDecodeError
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"
ABSENT = object()


def load_tiny_catalog() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def equipment_value(
    equipment_id: str = "fixture:weapon:training-blade",
    *,
    series_skill_id: object = ABSENT,
    group_skill_id: object = ABSENT,
    allows_series_skill_assignment: object = ABSENT,
    allows_group_skill_assignment: object = ABSENT,
) -> dict[str, object]:
    value: dict[str, object] = {
        "equipment_id": equipment_id,
        "part": "weapon",
        "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
        "slots": [{"kind": "weapon", "level": 1}],
    }
    if series_skill_id is not ABSENT:
        value["series_skill_id"] = series_skill_id
    if group_skill_id is not ABSENT:
        value["group_skill_id"] = group_skill_id
    if allows_series_skill_assignment is not ABSENT:
        value["allows_series_skill_assignment"] = allows_series_skill_assignment
    if allows_group_skill_assignment is not ABSENT:
        value["allows_group_skill_assignment"] = allows_group_skill_assignment
    return value


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


def skill_rank_value(
    level: object = 1,
    required_pieces: object = None,
) -> dict[str, object]:
    return {"level": level, "required_pieces": required_pieces}


def skill_definition_value(
    skill_id: object = "skill:attack-boost",
    kind: object = "armor",
    ranks: object = None,
    display_name: object = ABSENT,
) -> dict[str, object]:
    value: dict[str, object] = {
        "skill_id": skill_id,
        "kind": kind,
        "ranks": [skill_rank_value()] if ranks is None else ranks,
    }
    if display_name is not ABSENT:
        value["display_name"] = display_name
    return value


def series_skill_definition_value(
    skill_id: str = "skill:fixture-series-bonus",
) -> dict[str, object]:
    return skill_definition_value(
        skill_id=skill_id,
        kind="set",
        ranks=[skill_rank_value(1, 2), skill_rank_value(2, 4)],
    )


def group_skill_definition_value(
    skill_id: str = "skill:fixture-group-bonus",
) -> dict[str, object]:
    return skill_definition_value(
        skill_id=skill_id,
        kind="group",
        ranks=[skill_rank_value(1, 3)],
    )


def appraisal_skill_group_value(
    group_id: object = "fixture:appraisal-group:A",
    skills: object = ABSENT,
) -> dict[str, object]:
    return {
        "group_id": group_id,
        "skills": (
            [{"skill_id": "skill:attack-boost", "level": 1}]
            if skills is ABSENT
            else skills
        ),
    }


def appraisal_pattern_value(
    pattern_id: object = "fixture:appraisal-pattern:r8-a",
    rarity: object = 8,
    skill_group_ids: object = ABSENT,
    slots: object = ABSENT,
) -> dict[str, object]:
    return {
        "pattern_id": pattern_id,
        "rarity": rarity,
        "skill_group_ids": (
            ["fixture:appraisal-group:A"]
            if skill_group_ids is ABSENT
            else skill_group_ids
        ),
        "slots": [] if slots is ABSENT else slots,
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


def skills_generator() -> Iterator[dict[str, object]]:
    yield skill_definition_value()


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
    assert equipment.series_skill_id is None
    assert equipment.group_skill_id is None
    assert equipment.allows_series_skill_assignment is False
    assert equipment.allows_group_skill_assignment is False


def test_decode_equipment_definition_accepts_explicit_null_memberships() -> None:
    equipment = decode_equipment_definition(
        value=equipment_value(series_skill_id=None, group_skill_id=None),
    )

    assert equipment.series_skill_id is None
    assert equipment.group_skill_id is None


def test_decode_equipment_definition_accepts_explicit_false_assignment_flags() -> None:
    equipment = decode_equipment_definition(
        value=equipment_value(
            allows_series_skill_assignment=False,
            allows_group_skill_assignment=False,
        ),
    )

    assert equipment.allows_series_skill_assignment is False
    assert equipment.allows_group_skill_assignment is False


@pytest.mark.parametrize(
    ("series_enabled", "group_enabled"),
    [(True, False), (False, True), (True, True)],
)
def test_decode_equipment_definition_accepts_assignment_flags(
    series_enabled: bool,
    group_enabled: bool,
) -> None:
    equipment = decode_equipment_definition(
        value=equipment_value(
            allows_series_skill_assignment=series_enabled,
            allows_group_skill_assignment=group_enabled,
        ),
    )

    assert equipment.allows_series_skill_assignment is series_enabled
    assert equipment.allows_group_skill_assignment is group_enabled


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
@pytest.mark.parametrize("invalid_value", [None, 0, 1, "true", [], {}])
def test_decode_equipment_definition_wraps_invalid_assignment_flag_types(
    field_name: str,
    invalid_value: object,
) -> None:
    value = equipment_value()
    value[field_name] = invalid_value

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment")

    assert exc_info.value.path == "$.equipment"
    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
def test_decode_equipment_definition_wraps_non_weapon_assignment_error(
    field_name: str,
) -> None:
    value = alternate_equipment_value()
    value[field_name] = True

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment")

    assert exc_info.value.path == "$.equipment"
    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("membership_field", "assignment_field"),
    [
        ("series_skill_id", "allows_series_skill_assignment"),
        ("group_skill_id", "allows_group_skill_assignment"),
    ],
)
def test_decode_equipment_definition_wraps_fixed_membership_assignment_conflict(
    membership_field: str,
    assignment_field: str,
) -> None:
    value = equipment_value()
    value[membership_field] = "skill:fixture-bonus"
    value[assignment_field] = True

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment")

    assert assignment_field in exc_info.value.detail
    assert membership_field in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("value", "expected_series_skill_id", "expected_group_skill_id"),
    [
        (
            equipment_value(series_skill_id="skill:fixture-series-bonus"),
            "skill:fixture-series-bonus",
            None,
        ),
        (
            equipment_value(group_skill_id="skill:fixture-group-bonus"),
            None,
            "skill:fixture-group-bonus",
        ),
        (
            equipment_value(
                series_skill_id="skill:fixture-series-bonus",
                group_skill_id="skill:fixture-group-bonus",
            ),
            "skill:fixture-series-bonus",
            "skill:fixture-group-bonus",
        ),
    ],
)
def test_decode_equipment_definition_accepts_memberships(
    value: dict[str, object],
    expected_series_skill_id: str | None,
    expected_group_skill_id: str | None,
) -> None:
    equipment = decode_equipment_definition(value=value)

    assert equipment.series_skill_id == expected_series_skill_id
    assert equipment.group_skill_id == expected_group_skill_id


def test_decode_equipment_membership_keys_are_order_independent() -> None:
    value = {
        "group_skill_id": "skill:fixture-group-bonus",
        "slots": [{"kind": "armor", "level": 1}],
        "series_skill_id": "skill:fixture-series-bonus",
        "skills": [],
        "part": "head",
        "equipment_id": "fixture:head:precision-alpha",
    }

    equipment = decode_equipment_definition(value=value)

    assert equipment.series_skill_id == "skill:fixture-series-bonus"
    assert equipment.group_skill_id == "skill:fixture-group-bonus"


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
@pytest.mark.parametrize(
    ("invalid_value", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (1.5, TypeError),
        ([], TypeError),
        ("", ValueError),
        (" ", ValueError),
        (" skill:fixture-bonus", ValueError),
        ("skill:fixture-bonus ", ValueError),
    ],
)
def test_decode_equipment_definition_wraps_invalid_membership_errors(
    field_name: str,
    invalid_value: object,
    expected_cause: type[Exception],
) -> None:
    value = equipment_value()
    value[field_name] = invalid_value

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment")

    assert exc_info.value.path == "$.equipment"
    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
def test_decode_equipment_definition_rejects_membership_string_subclass(
    field_name: str,
) -> None:
    class MembershipId(str):
        pass

    value = equipment_value()
    value[field_name] = MembershipId("skill:fixture-bonus")

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment")

    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_decode_equipment_definition_still_rejects_unknown_keys() -> None:
    value = equipment_value(
        series_skill_id="skill:fixture-series-bonus",
        group_skill_id="skill:fixture-group-bonus",
    )
    value["unexpected"] = True

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment")

    assert exc_info.value.path == "$.equipment"
    assert "unexpected" in exc_info.value.detail


@pytest.mark.parametrize("required_key", ["equipment_id", "part", "skills", "slots"])
def test_decode_equipment_definition_still_requires_original_keys(
    required_key: str,
) -> None:
    value = equipment_value(
        series_skill_id="skill:fixture-series-bonus",
        group_skill_id="skill:fixture-group-bonus",
    )
    del value[required_key]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment")

    assert exc_info.value.path == "$.equipment"
    assert required_key in exc_info.value.detail


def test_decode_catalog_accepts_valid_equipment_membership_references() -> None:
    value = catalog_value()
    value["equipment"] = [
        equipment_value(
            series_skill_id="skill:fixture-series-bonus",
            group_skill_id="skill:fixture-group-bonus",
        )
    ]
    value["skills"] = [
        series_skill_definition_value(),
        group_skill_definition_value(),
    ]

    catalog = decode_catalog(value=value)

    assert catalog.equipment[0].series_skill_id == "skill:fixture-series-bonus"
    assert catalog.equipment[0].group_skill_id == "skill:fixture-group-bonus"


def test_decode_catalog_accepts_dual_assignment_with_available_skill_kinds() -> None:
    value = catalog_value()
    value["equipment"] = [
        equipment_value(
            allows_series_skill_assignment=True,
            allows_group_skill_assignment=True,
        )
    ]
    value["skills"] = [
        series_skill_definition_value(),
        group_skill_definition_value(),
    ]

    catalog = decode_catalog(value=value)

    assert catalog.equipment[0].allows_series_skill_assignment is True
    assert catalog.equipment[0].allows_group_skill_assignment is True


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
def test_decode_catalog_wraps_assignment_availability_failure_at_root(
    field_name: str,
) -> None:
    equipment = equipment_value()
    equipment[field_name] = True
    value = catalog_value()
    value["equipment"] = [equipment]
    value["skills"] = []

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "equipment" in exc_info.value.detail
    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("field_name", "missing_skill_id"),
    [
        ("series_skill_id", "skill:missing-series"),
        ("group_skill_id", "skill:missing-group"),
    ],
)
def test_decode_catalog_wraps_missing_membership_reference_at_root(
    field_name: str,
    missing_skill_id: str,
) -> None:
    equipment = equipment_value()
    equipment[field_name] = missing_skill_id
    value = catalog_value()
    value["equipment"] = [equipment]
    value["skills"] = []

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "equipment" in exc_info.value.detail
    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("field_name", "wrong_skill"),
    [
        (
            "series_skill_id",
            skill_definition_value("skill:wrong-armor", "armor"),
        ),
        (
            "series_skill_id",
            skill_definition_value("skill:wrong-weapon", "weapon"),
        ),
        (
            "series_skill_id",
            group_skill_definition_value("skill:wrong-group"),
        ),
        (
            "group_skill_id",
            skill_definition_value("skill:wrong-armor", "armor"),
        ),
        (
            "group_skill_id",
            skill_definition_value("skill:wrong-weapon", "weapon"),
        ),
        (
            "group_skill_id",
            series_skill_definition_value("skill:wrong-series"),
        ),
    ],
)
def test_decode_catalog_wraps_wrong_kind_membership_reference_at_root(
    field_name: str,
    wrong_skill: dict[str, object],
) -> None:
    equipment = equipment_value()
    equipment[field_name] = wrong_skill["skill_id"]
    value = catalog_value()
    value["equipment"] = [equipment]
    value["skills"] = [wrong_skill]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "equipment" in exc_info.value.detail
    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_decode_catalog_without_membership_keys_remains_backward_compatible() -> None:
    catalog = decode_catalog(value=catalog_value())

    assert catalog.equipment[0].series_skill_id is None
    assert catalog.equipment[0].group_skill_id is None
    assert catalog.equipment[0].allows_series_skill_assignment is False
    assert catalog.equipment[0].allows_group_skill_assignment is False


def test_decode_catalog_accepts_explicit_null_memberships_without_skills() -> None:
    value = catalog_value()
    value["equipment"] = [
        equipment_value(series_skill_id=None, group_skill_id=None),
    ]

    catalog = decode_catalog(value=value)

    assert catalog.equipment[0].series_skill_id is None
    assert catalog.equipment[0].group_skill_id is None


def test_catalog_decode_error_still_imports_directly() -> None:
    error = CatalogDecodeError(path="$.catalog", detail="invalid object")

    assert str(error) == "$.catalog: invalid object"


@pytest.mark.parametrize(
    ("kind_value", "expected_kind", "ranks"),
    [
        ("armor", SkillKind.ARMOR, [skill_rank_value(1), skill_rank_value(2)]),
        ("weapon", SkillKind.WEAPON, [skill_rank_value(1)]),
        (
            "set",
            SkillKind.SERIES,
            [skill_rank_value(1, 2), skill_rank_value(2, 4)],
        ),
        ("group", SkillKind.GROUP, [skill_rank_value(1, 3)]),
    ],
)
def test_decode_skill_definition_converts_each_skill_kind(
    kind_value: str,
    expected_kind: SkillKind,
    ranks: list[dict[str, object]],
) -> None:
    decoded = decode_skill_definition(
        value=skill_definition_value(kind=kind_value, ranks=ranks),
    )

    assert decoded == SkillDefinition(
        skill_id="skill:attack-boost",
        kind=expected_kind,
        ranks=tuple(
            SkillRankDefinition(
                level=rank_value["level"],  # type: ignore[arg-type]
                required_pieces=rank_value["required_pieces"],  # type: ignore[arg-type]
            )
            for rank_value in ranks
        ),
    )


def test_decode_skill_rank_definition_converts_normal_rank() -> None:
    decoded = decode_skill_rank_definition(
        value={"level": 2, "required_pieces": None},
    )

    assert decoded == SkillRankDefinition(level=2, required_pieces=None)


def test_decode_skill_rank_definition_converts_piece_threshold_rank() -> None:
    decoded = decode_skill_rank_definition(
        value={"level": 2, "required_pieces": 4},
    )

    assert decoded == SkillRankDefinition(level=2, required_pieces=4)


@pytest.mark.parametrize("value", [None, "rank", [], ()])
def test_decode_skill_rank_definition_rejects_non_dict(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_rank_definition(value=value, path="$.rank")

    assert exc_info.value.path == "$.rank"
    assert "object" in exc_info.value.detail


def test_decode_skill_rank_definition_rejects_dict_subclass() -> None:
    class RankDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_rank_definition(
            value=RankDict(skill_rank_value()),
            path="$.rank",
        )

    assert exc_info.value.path == "$.rank"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        ({"required_pieces": None}, ("level",)),
        ({"level": 1}, ("required_pieces",)),
        (
            {"level": 1, "required_pieces": None, "extra": True},
            ("extra",),
        ),
        ({}, ("level", "required_pieces")),
    ],
)
def test_decode_skill_rank_definition_rejects_invalid_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_rank_definition(value=value, path="$.rank")

    assert exc_info.value.path == "$.rank"
    for fragment in expected_fragments:
        assert fragment in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_field", "expected_cause"),
    [
        (skill_rank_value(level=True), "level", TypeError),
        (skill_rank_value(level=0), "level", ValueError),
        (skill_rank_value(required_pieces=True), "required_pieces", TypeError),
        (skill_rank_value(required_pieces=0), "required_pieces", ValueError),
    ],
)
def test_decode_skill_rank_definition_wraps_domain_errors(
    value: dict[str, object],
    expected_field: str,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_rank_definition(value=value, path="$.rank")

    assert exc_info.value.path == "$.rank"
    assert expected_field in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize("value", [None, "skill", [], ()])
def test_decode_skill_definition_rejects_non_dict(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(value=value, path="$.skill")

    assert exc_info.value.path == "$.skill"
    assert "object" in exc_info.value.detail


def test_decode_skill_definition_rejects_dict_subclass() -> None:
    class SkillDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=SkillDict(skill_definition_value()),
            path="$.skill",
        )

    assert exc_info.value.path == "$.skill"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        ({"kind": "armor", "ranks": [skill_rank_value()]}, ("skill_id",)),
        (
            {"skill_id": "skill:test", "ranks": [skill_rank_value()]},
            ("kind",),
        ),
        ({"skill_id": "skill:test", "kind": "armor"}, ("ranks",)),
        (
            dict(skill_definition_value(), extra=True),
            ("extra",),
        ),
        ({}, ("skill_id", "kind", "ranks")),
    ],
)
def test_decode_skill_definition_rejects_invalid_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(value=value, path="$.skill")

    assert exc_info.value.path == "$.skill"
    for fragment in expected_fragments:
        assert fragment in exc_info.value.detail


@pytest.mark.parametrize(
    "ranks",
    [
        (skill_rank_value(),),
        {"level": 1, "required_pieces": None},
        {("level", 1)},
        skills_generator(),
        None,
    ],
)
def test_decode_skill_definition_rejects_non_list_ranks(ranks: object) -> None:
    value = skill_definition_value()
    value["ranks"] = ranks

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=value,
            path="$.skill",
        )

    assert exc_info.value.path == "$.skill.ranks"
    assert "ranks" in exc_info.value.detail


def test_decode_skill_definition_rejects_ranks_list_subclass() -> None:
    class RankList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=skill_definition_value(ranks=RankList([skill_rank_value()])),
            path="$.skill",
        )

    assert exc_info.value.path == "$.skill.ranks"
    assert "ranks" in exc_info.value.detail


def test_decode_skill_definition_rejects_empty_ranks() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=skill_definition_value(ranks=[]),
            path="$.skill",
        )

    assert exc_info.value.path == "$.skill.ranks"
    assert "empty" in exc_info.value.detail


def test_decode_skill_definition_preserves_nested_rank_error_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=skill_definition_value(
                kind="set",
                ranks=[skill_rank_value(1, 2), skill_rank_value(0, 4)],
            ),
            path="$.catalog.skills[1]",
        )

    assert exc_info.value.path == "$.catalog.skills[1].ranks[1]"
    assert "level" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("kind", "expected_cause"),
    [
        ("series", ValueError),
        ("normal", ValueError),
        ("Armor", ValueError),
        ("", ValueError),
        (1, TypeError),
        (True, TypeError),
        (None, TypeError),
    ],
)
def test_decode_skill_definition_rejects_invalid_kind_values(
    kind: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=skill_definition_value(kind=kind),
            path="$.skill",
        )

    assert exc_info.value.path == "$.skill"
    assert "kind" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    ("value", "expected_fragment"),
    [
        (skill_definition_value(skill_id=""), "skill_id"),
        (
            skill_definition_value(
                kind="armor",
                ranks=[skill_rank_value(1, 2)],
            ),
            "ranks",
        ),
        (
            skill_definition_value(
                kind="set",
                ranks=[skill_rank_value(1, None)],
            ),
            "ranks",
        ),
        (
            skill_definition_value(
                kind="group",
                ranks=[skill_rank_value(1, 3), skill_rank_value(2, 3)],
            ),
            "ranks",
        ),
        (
            skill_definition_value(
                kind="set",
                ranks=[skill_rank_value(1, 2), skill_rank_value(3, 4)],
            ),
            "ranks",
        ),
    ],
)
def test_decode_skill_definition_wraps_domain_cross_invariant_errors(
    value: dict[str, object],
    expected_fragment: str,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(value=value, path="$.skill")

    assert exc_info.value.path == "$.skill"
    assert expected_fragment in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_skill_metadata_decoders_are_keyword_only() -> None:
    for decoder in (decode_skill_rank_definition, decode_skill_definition):
        signature = inspect.signature(decoder)

        assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY


def test_decode_catalog_without_skills_keeps_backward_compatible_empty_tuple() -> None:
    decoded = decode_catalog(value=catalog_value())

    assert decoded.skills == ()


def test_decode_catalog_with_empty_skills_list_returns_empty_tuple() -> None:
    value = catalog_value()
    value["skills"] = []

    decoded = decode_catalog(value=value)

    assert decoded.skills == ()


def test_decode_catalog_with_skills_preserves_order() -> None:
    value = catalog_value()
    value["skills"] = [
        skill_definition_value("skill:attack-boost", "armor"),
        skill_definition_value(
            "skill:series-bonus",
            "set",
            [skill_rank_value(1, 2), skill_rank_value(2, 4)],
        ),
        skill_definition_value(
            "skill:group-bonus",
            "group",
            [skill_rank_value(1, 3)],
        ),
    ]

    decoded = decode_catalog(value=value)

    assert [skill.skill_id for skill in decoded.skills] == [
        "skill:attack-boost",
        "skill:series-bonus",
        "skill:group-bonus",
    ]


@pytest.mark.parametrize(
    "skills",
    [
        (skill_definition_value(),),
        {"skill_id": "skill:attack-boost"},
        {("skill:attack-boost", "armor")},
        skills_generator(),
        None,
    ],
)
def test_decode_catalog_rejects_non_list_skills(skills: object) -> None:
    value = catalog_value()
    value["skills"] = skills

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.skills"
    assert "skills" in exc_info.value.detail


def test_decode_catalog_rejects_skills_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    value = catalog_value()
    value["skills"] = SkillList([skill_definition_value()])

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.skills"
    assert "skills" in exc_info.value.detail


def test_decode_catalog_preserves_nested_skill_error_path() -> None:
    value = catalog_value()
    value["skills"] = [
        skill_definition_value(),
        skill_definition_value(
            skill_id="skill:series-bonus",
            kind="set",
            ranks=[skill_rank_value(1, 2), skill_rank_value(0, 4)],
        ),
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.skills[1].ranks[1]"
    assert_nested_error_not_wrapped(exc_info.value)


def test_decode_catalog_wraps_duplicate_skill_id_error_at_root() -> None:
    value = catalog_value()
    value["skills"] = [
        skill_definition_value(),
        skill_definition_value(kind="weapon"),
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "skills" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_decode_appraisal_skill_group_converts_valid_ordered_object() -> None:
    value = appraisal_skill_group_value(
        group_id="fixture:appraisal-group:B",
        skills=[
            {"skill_id": "skill:attack-boost", "level": 2},
            {"skill_id": "skill:weapon-technique", "level": 1},
        ],
    )

    decoded = decode_appraisal_charm_skill_group_definition(value=value)

    assert decoded == AppraisalCharmSkillGroupDefinition(
        group_id="fixture:appraisal-group:B",
        skills=(
            SkillContribution("skill:attack-boost", 2),
            SkillContribution("skill:weapon-technique", 1),
        ),
    )


@pytest.mark.parametrize("value", [None, "group", [], ()])
def test_decode_appraisal_skill_group_rejects_non_dict(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=value,
            path="$.group",
        )

    assert exc_info.value.path == "$.group"
    assert "object" in exc_info.value.detail


def test_decode_appraisal_skill_group_rejects_dict_subclass() -> None:
    class GroupDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=GroupDict(appraisal_skill_group_value()),
            path="$.group",
        )

    assert exc_info.value.path == "$.group"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        ({"skills": []}, ("group_id",)),
        ({"group_id": "fixture:appraisal-group:A"}, ("skills",)),
        (
            dict(appraisal_skill_group_value(), extra=True),
            ("extra",),
        ),
        ({}, ("group_id", "skills")),
    ],
)
def test_decode_appraisal_skill_group_rejects_invalid_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=value,
            path="$.group",
        )

    assert exc_info.value.path == "$.group"
    for fragment in expected_fragments:
        assert fragment in exc_info.value.detail


@pytest.mark.parametrize(
    "skills",
    [
        ({"skill_id": "skill:attack-boost", "level": 1},),
        {"skill_id": "skill:attack-boost", "level": 1},
        skills_generator(),
        None,
    ],
)
def test_decode_appraisal_skill_group_rejects_non_list_skills(
    skills: object,
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=appraisal_skill_group_value(skills=skills),
            path="$.group",
        )

    assert exc_info.value.path == "$.group.skills"
    assert "skills" in exc_info.value.detail


def test_decode_appraisal_skill_group_rejects_skills_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=appraisal_skill_group_value(
                skills=SkillList([{"skill_id": "skill:attack-boost", "level": 1}])
            ),
            path="$.group",
        )

    assert exc_info.value.path == "$.group.skills"


def test_decode_appraisal_skill_group_rejects_empty_skills() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=appraisal_skill_group_value(skills=[]),
            path="$.group",
        )

    assert exc_info.value.path == "$.group.skills"
    assert "empty" in exc_info.value.detail


def test_decode_appraisal_skill_group_preserves_nested_contribution_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=appraisal_skill_group_value(
                skills=[
                    {"skill_id": "skill:attack-boost", "level": 1},
                    {"skill_id": "skill:critical-eye", "level": 0},
                ]
            ),
            path="$.catalog.appraisal_charm_skill_groups[2]",
        )

    assert exc_info.value.path == "$.catalog.appraisal_charm_skill_groups[2].skills[1]"
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("group_id", "expected_cause"),
    [
        (None, TypeError),
        (1, TypeError),
        ("", ValueError),
        (" group:A", ValueError),
    ],
)
def test_decode_appraisal_skill_group_wraps_identifier_errors(
    group_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=appraisal_skill_group_value(group_id=group_id),
            path="$.group",
        )

    assert exc_info.value.path == "$.group"
    assert "group_id" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_decode_appraisal_skill_group_wraps_duplicate_skill_error() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_skill_group_definition(
            value=appraisal_skill_group_value(
                skills=[
                    {"skill_id": "skill:attack-boost", "level": 1},
                    {"skill_id": "skill:attack-boost", "level": 2},
                ]
            ),
            path="$.group",
        )

    assert exc_info.value.path == "$.group"
    assert "skills" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_decode_appraisal_pattern_converts_valid_atomic_object() -> None:
    value = appraisal_pattern_value(
        pattern_id="fixture:appraisal-pattern:r8-b-a-j-w1-a1-a1",
        skill_group_ids=[
            "fixture:appraisal-group:B",
            "fixture:appraisal-group:A",
            "fixture:appraisal-group:J",
        ],
        slots=[
            {"kind": "weapon", "level": 1},
            {"kind": "armor", "level": 1},
            {"kind": "armor", "level": 1},
        ],
    )

    decoded = decode_appraisal_charm_pattern_definition(value=value)

    assert decoded == AppraisalCharmPatternDefinition(
        pattern_id="fixture:appraisal-pattern:r8-b-a-j-w1-a1-a1",
        rarity=8,
        skill_group_ids=(
            "fixture:appraisal-group:B",
            "fixture:appraisal-group:A",
            "fixture:appraisal-group:J",
        ),
        slots=(
            DecorationSlot(DecorationKind.WEAPON, 1),
            DecorationSlot(DecorationKind.ARMOR, 1),
            DecorationSlot(DecorationKind.ARMOR, 1),
        ),
    )


@pytest.mark.parametrize("value", [None, "pattern", [], ()])
def test_decode_appraisal_pattern_rejects_non_dict(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=value,
            path="$.pattern",
        )

    assert exc_info.value.path == "$.pattern"
    assert "object" in exc_info.value.detail


def test_decode_appraisal_pattern_rejects_dict_subclass() -> None:
    class PatternDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=PatternDict(appraisal_pattern_value()),
            path="$.pattern",
        )

    assert exc_info.value.path == "$.pattern"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        (
            {"rarity": 8, "skill_group_ids": ["group:A"], "slots": []},
            ("pattern_id",),
        ),
        (
            {
                "pattern_id": "pattern:A",
                "skill_group_ids": ["group:A"],
                "slots": [],
            },
            ("rarity",),
        ),
        (
            {"pattern_id": "pattern:A", "rarity": 8, "slots": []},
            ("skill_group_ids",),
        ),
        (
            {
                "pattern_id": "pattern:A",
                "rarity": 8,
                "skill_group_ids": ["group:A"],
            },
            ("slots",),
        ),
        (dict(appraisal_pattern_value(), extra=True), ("extra",)),
        ({}, ("pattern_id", "rarity", "skill_group_ids", "slots")),
    ],
)
def test_decode_appraisal_pattern_rejects_invalid_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=value,
            path="$.pattern",
        )

    assert exc_info.value.path == "$.pattern"
    for fragment in expected_fragments:
        assert fragment in exc_info.value.detail


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("skill_group_ids", ("fixture:appraisal-group:A",)),
        ("skill_group_ids", {"fixture:appraisal-group:A"}),
        ("skill_group_ids", group_skill_definition_value()),
        ("skill_group_ids", None),
        ("slots", ({"kind": "armor", "level": 1},)),
        ("slots", {"kind": "armor", "level": 1}),
        ("slots", skills_generator()),
        ("slots", None),
    ],
)
def test_decode_appraisal_pattern_rejects_non_list_fields(
    field_name: str,
    invalid_value: object,
) -> None:
    value = appraisal_pattern_value()
    value[field_name] = invalid_value

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=value,
            path="$.pattern",
        )

    assert exc_info.value.path == f"$.pattern.{field_name}"
    assert field_name in exc_info.value.detail


@pytest.mark.parametrize("field_name", ["skill_group_ids", "slots"])
def test_decode_appraisal_pattern_rejects_list_subclasses(field_name: str) -> None:
    class FieldList(list[object]):
        pass

    value = appraisal_pattern_value()
    value[field_name] = FieldList(value[field_name])  # type: ignore[arg-type]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=value,
            path="$.pattern",
        )

    assert exc_info.value.path == f"$.pattern.{field_name}"


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_cause"),
    [
        ("pattern_id", "", ValueError),
        ("pattern_id", 1, TypeError),
        ("rarity", 0, ValueError),
        ("rarity", True, TypeError),
    ],
)
def test_decode_appraisal_pattern_wraps_identifier_and_rarity_errors(
    field_name: str,
    invalid_value: object,
    expected_cause: type[Exception],
) -> None:
    value = appraisal_pattern_value()
    value[field_name] = invalid_value

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=value,
            path="$.pattern",
        )

    assert exc_info.value.path == "$.pattern"
    assert field_name in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    "skill_group_ids",
    [
        [],
        ["group:A", "group:B", "group:C", "group:D"],
    ],
)
def test_decode_appraisal_pattern_wraps_group_count_errors(
    skill_group_ids: list[str],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=appraisal_pattern_value(skill_group_ids=skill_group_ids),
            path="$.pattern",
        )

    assert exc_info.value.path == "$.pattern"
    assert "skill_group_ids" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    ("invalid_group_id", "expected_cause"),
    [
        (None, TypeError),
        (1, TypeError),
        (True, TypeError),
        ("", ValueError),
        (" group:A", ValueError),
    ],
)
def test_decode_appraisal_pattern_wraps_invalid_group_id_values(
    invalid_group_id: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=appraisal_pattern_value(skill_group_ids=[invalid_group_id]),
            path="$.pattern",
        )

    assert exc_info.value.path == "$.pattern"
    assert "skill_group_ids" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_decode_appraisal_pattern_preserves_nested_slot_error_path() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=appraisal_pattern_value(
                slots=[
                    {"kind": "weapon", "level": 1},
                    {"kind": "armor", "level": 0},
                ]
            ),
            path="$.catalog.appraisal_charm_patterns[1]",
        )

    assert exc_info.value.path == "$.catalog.appraisal_charm_patterns[1].slots[1]"
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_decode_appraisal_pattern_wraps_slot_layout_domain_error() -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_appraisal_charm_pattern_definition(
            value=appraisal_pattern_value(
                slots=[
                    {"kind": "armor", "level": 1},
                    {"kind": "weapon", "level": 1},
                ]
            ),
            path="$.pattern",
        )

    assert exc_info.value.path == "$.pattern"
    assert "slots" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_appraisal_decoders_are_keyword_only() -> None:
    for decoder in (
        decode_appraisal_charm_skill_group_definition,
        decode_appraisal_charm_pattern_definition,
    ):
        signature = inspect.signature(decoder)

        assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY


def test_decode_catalog_defaults_appraisal_rule_fields_to_empty_tuples() -> None:
    decoded = decode_catalog(value=catalog_value())

    assert decoded.appraisal_charm_skill_groups == ()
    assert decoded.appraisal_charm_patterns == ()


def test_decode_catalog_accepts_present_empty_appraisal_rule_lists() -> None:
    value = catalog_value()
    value["appraisal_charm_skill_groups"] = []
    value["appraisal_charm_patterns"] = []

    decoded = decode_catalog(value=value)

    assert decoded.appraisal_charm_skill_groups == ()
    assert decoded.appraisal_charm_patterns == ()


def test_decode_catalog_preserves_populated_appraisal_rule_order() -> None:
    value = catalog_value()
    value["skills"] = [
        skill_definition_value("skill:attack-boost", "armor"),
        skill_definition_value("skill:weapon-technique", "weapon"),
    ]
    value["appraisal_charm_skill_groups"] = [
        appraisal_skill_group_value(
            "fixture:appraisal-group:B",
            [{"skill_id": "skill:weapon-technique", "level": 1}],
        ),
        appraisal_skill_group_value("fixture:appraisal-group:A"),
    ]
    value["appraisal_charm_patterns"] = [
        appraisal_pattern_value(
            "fixture:appraisal-pattern:r8-b-a",
            skill_group_ids=[
                "fixture:appraisal-group:B",
                "fixture:appraisal-group:A",
            ],
        ),
        appraisal_pattern_value(
            "fixture:appraisal-pattern:r7-a",
            rarity=7,
        ),
    ]

    decoded = decode_catalog(value=value)

    assert [group.group_id for group in decoded.appraisal_charm_skill_groups] == [
        "fixture:appraisal-group:B",
        "fixture:appraisal-group:A",
    ]
    assert [pattern.pattern_id for pattern in decoded.appraisal_charm_patterns] == [
        "fixture:appraisal-pattern:r8-b-a",
        "fixture:appraisal-pattern:r7-a",
    ]


def appraisal_group_value_generator() -> Iterator[dict[str, object]]:
    yield appraisal_skill_group_value()


def appraisal_pattern_value_generator() -> Iterator[dict[str, object]]:
    yield appraisal_pattern_value()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("appraisal_charm_skill_groups", (appraisal_skill_group_value(),)),
        ("appraisal_charm_skill_groups", appraisal_skill_group_value()),
        ("appraisal_charm_skill_groups", appraisal_group_value_generator()),
        ("appraisal_charm_skill_groups", None),
        ("appraisal_charm_patterns", (appraisal_pattern_value(),)),
        ("appraisal_charm_patterns", appraisal_pattern_value()),
        ("appraisal_charm_patterns", appraisal_pattern_value_generator()),
        ("appraisal_charm_patterns", None),
    ],
)
def test_decode_catalog_rejects_non_list_appraisal_rule_fields(
    field_name: str,
    invalid_value: object,
) -> None:
    value = catalog_value()
    value[field_name] = invalid_value

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == f"$.catalog.{field_name}"
    assert field_name in exc_info.value.detail


@pytest.mark.parametrize(
    ("field_name", "item"),
    [
        ("appraisal_charm_skill_groups", appraisal_skill_group_value()),
        ("appraisal_charm_patterns", appraisal_pattern_value()),
    ],
)
def test_decode_catalog_rejects_appraisal_rule_list_subclasses(
    field_name: str,
    item: dict[str, object],
) -> None:
    class RuleList(list[object]):
        pass

    value = catalog_value()
    value[field_name] = RuleList([item])

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == f"$.catalog.{field_name}"


def test_decode_catalog_preserves_nested_appraisal_group_error_path() -> None:
    value = catalog_value()
    value["appraisal_charm_skill_groups"] = [
        appraisal_skill_group_value(),
        appraisal_skill_group_value(skills=[{"skill_id": "skill:test", "level": 0}]),
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.appraisal_charm_skill_groups[1].skills[0]"
    assert_nested_error_not_wrapped(exc_info.value)


def test_decode_catalog_preserves_nested_appraisal_pattern_error_path() -> None:
    value = catalog_value()
    value["appraisal_charm_patterns"] = [
        appraisal_pattern_value(
            slots=[{"kind": "armor", "level": 0}],
        )
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog.appraisal_charm_patterns[0].slots[0]"
    assert_nested_error_not_wrapped(exc_info.value)


def test_decode_catalog_wraps_missing_appraisal_skill_reference_at_root() -> None:
    value = catalog_value()
    value["appraisal_charm_skill_groups"] = [
        appraisal_skill_group_value(
            skills=[{"skill_id": "skill:missing", "level": 1}],
        )
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "appraisal_charm_skill_groups" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "skill_value",
    [series_skill_definition_value(), group_skill_definition_value()],
)
def test_decode_catalog_wraps_invalid_appraisal_skill_kind_at_root(
    skill_value: dict[str, object],
) -> None:
    value = catalog_value()
    value["skills"] = [skill_value]
    value["appraisal_charm_skill_groups"] = [
        appraisal_skill_group_value(
            skills=[{"skill_id": skill_value["skill_id"], "level": 1}],
        )
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "appraisal_charm_skill_groups" in exc_info.value.detail
    assert "armor or weapon" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_decode_catalog_wraps_appraisal_level_above_rank_at_root() -> None:
    value = catalog_value()
    value["skills"] = [skill_definition_value()]
    value["appraisal_charm_skill_groups"] = [
        appraisal_skill_group_value(
            skills=[{"skill_id": "skill:attack-boost", "level": 2}],
        )
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "maximum" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_decode_catalog_wraps_missing_pattern_group_at_root() -> None:
    value = catalog_value()
    value["appraisal_charm_patterns"] = [
        appraisal_pattern_value(skill_group_ids=["fixture:appraisal-group:missing"])
    ]

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_catalog(value=value, path="$.catalog")

    assert exc_info.value.path == "$.catalog"
    assert "appraisal_charm_patterns" in exc_info.value.detail
    assert "skill_group_ids" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_appraisal_decoders_are_not_exported_from_catalog_package() -> None:
    import mhwilds_skill_sim.catalog as catalog_package

    assert not hasattr(
        catalog_package,
        "decode_appraisal_charm_skill_group_definition",
    )
    assert not hasattr(
        catalog_package,
        "decode_appraisal_charm_pattern_definition",
    )


def test_decode_normalized_skill_without_display_name_remains_valid() -> None:
    decoded = decode_skill_definition(value=skill_definition_value())

    assert decoded.display_name is None


def test_decode_normalized_skill_accepts_explicit_null_display_name() -> None:
    decoded = decode_skill_definition(
        value=skill_definition_value(display_name=None),
    )

    assert decoded.display_name is None


@pytest.mark.parametrize(
    "display_name",
    ["攻撃力強化（テスト）", "Attack Boost (Test)"],
)
def test_decode_normalized_skill_preserves_valid_display_name(
    display_name: str,
) -> None:
    decoded = decode_skill_definition(
        value=skill_definition_value(display_name=display_name),
    )

    assert decoded.display_name == display_name


def test_decode_normalized_skill_display_name_key_order_is_independent() -> None:
    value = {
        "display_name": "攻撃力強化（テスト）",
        "ranks": [skill_rank_value()],
        "kind": "armor",
        "skill_id": "skill:attack-boost",
    }

    decoded = decode_skill_definition(value=value)

    assert decoded == SkillDefinition(
        skill_id="skill:attack-boost",
        kind=SkillKind.ARMOR,
        ranks=(SkillRankDefinition(1, None),),
        display_name="攻撃力強化（テスト）",
    )


@pytest.mark.parametrize(
    ("display_name", "expected_cause"),
    [
        (True, TypeError),
        (1, TypeError),
        (1.5, TypeError),
        ("", ValueError),
        ("   ", ValueError),
        (" Attack Boost", ValueError),
        ("Attack Boost ", ValueError),
    ],
)
def test_decode_normalized_skill_wraps_invalid_display_name(
    display_name: object,
    expected_cause: type[Exception],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=skill_definition_value(display_name=display_name),
            path="$.skills[0]",
        )

    assert exc_info.value.path == "$.skills[0]"
    assert "display_name" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


def test_decode_normalized_skill_rejects_display_name_string_subclass() -> None:
    class DisplayName(str):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(
            value=skill_definition_value(
                display_name=DisplayName("Attack Boost"),
            ),
            path="$.skills[0]",
        )

    assert exc_info.value.path == "$.skills[0]"
    assert "display_name" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_decode_normalized_skill_with_display_name_still_rejects_unknown_key() -> None:
    value = skill_definition_value(display_name="Attack Boost")
    value["description"] = "must remain upstream-only"

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_skill_definition(value=value, path="$.skills[0]")

    assert exc_info.value.path == "$.skills[0]"
    assert "description" in exc_info.value.detail
    assert exc_info.value.__cause__ is None


def test_decode_catalog_preserves_normalized_skill_display_name() -> None:
    value = catalog_value()
    value["skills"] = [skill_definition_value(display_name="攻撃力強化（テスト）")]

    decoded = decode_catalog(value=value)

    assert decoded.skills[0].display_name == "攻撃力強化（テスト）"
