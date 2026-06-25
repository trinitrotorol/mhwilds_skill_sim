from __future__ import annotations

import copy
import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.catalog.decoder import (
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


def weapon_value() -> dict[str, object]:
    return {
        "equipment_id": "fixture:weapon:training-blade",
        "part": "weapon",
        "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
        "slots": [
            {"kind": "weapon", "level": 2},
            {"kind": "weapon", "level": 1},
        ],
    }


def armor_value() -> dict[str, object]:
    return {
        "equipment_id": "fixture:head:precision-alpha",
        "part": "head",
        "skills": [{"skill_id": "skill:critical-eye", "level": 1}],
        "slots": [{"kind": "armor", "level": 1}],
    }


def empty_equipment_value() -> dict[str, object]:
    return {
        "equipment_id": "fixture:charm:empty",
        "part": "charm",
        "skills": [],
        "slots": [],
    }


def skills_generator() -> Iterator[dict[str, object]]:
    yield {"skill_id": "skill:attack-boost", "level": 1}


def slots_generator() -> Iterator[dict[str, object]]:
    yield {"kind": "weapon", "level": 1}


def assert_nested_error_not_wrapped(error: CatalogDecodeError) -> None:
    assert not isinstance(error.__cause__, CatalogDecodeError)


def test_decode_equipment_definition_converts_weapon_with_skills_and_slots() -> None:
    equipment = decode_equipment_definition(value=weapon_value())

    assert isinstance(equipment, EquipmentDefinition)
    assert equipment.equipment_id == "fixture:weapon:training-blade"
    assert equipment.part is EquipmentPart.WEAPON
    assert type(equipment.skills) is tuple
    assert type(equipment.slots) is tuple
    assert equipment.skills == (SkillContribution("skill:attack-boost", 1),)
    assert equipment.slots == (
        DecorationSlot(DecorationKind.WEAPON, 2),
        DecorationSlot(DecorationKind.WEAPON, 1),
    )


def test_decode_equipment_definition_converts_armor_with_skills_and_slots() -> None:
    equipment = decode_equipment_definition(value=armor_value())

    assert isinstance(equipment, EquipmentDefinition)
    assert equipment.equipment_id == "fixture:head:precision-alpha"
    assert equipment.part is EquipmentPart.HEAD
    assert equipment.skills == (SkillContribution("skill:critical-eye", 1),)
    assert equipment.slots == (DecorationSlot(DecorationKind.ARMOR, 1),)


def test_decode_equipment_definition_accepts_empty_skills() -> None:
    value = weapon_value()
    value["skills"] = []

    equipment = decode_equipment_definition(value=value)

    assert equipment.skills == ()


def test_decode_equipment_definition_accepts_empty_slots() -> None:
    value = weapon_value()
    value["slots"] = []

    equipment = decode_equipment_definition(value=value)

    assert equipment.slots == ()


def test_decode_equipment_definition_accepts_empty_skills_and_slots() -> None:
    equipment = decode_equipment_definition(value=empty_equipment_value())

    assert equipment.skills == ()
    assert equipment.slots == ()


@pytest.mark.parametrize(
    ("part", "expected_part"),
    [
        ("weapon", EquipmentPart.WEAPON),
        ("head", EquipmentPart.HEAD),
        ("chest", EquipmentPart.CHEST),
        ("arms", EquipmentPart.ARMS),
        ("waist", EquipmentPart.WAIST),
        ("legs", EquipmentPart.LEGS),
        ("charm", EquipmentPart.CHARM),
    ],
)
def test_decode_equipment_definition_converts_all_parts(
    part: str,
    expected_part: EquipmentPart,
) -> None:
    value = empty_equipment_value()
    value["part"] = part

    equipment = decode_equipment_definition(value=value)

    assert equipment.part is expected_part


def test_decode_equipment_definition_preserves_skill_and_slot_order() -> None:
    value = {
        "equipment_id": "fixture:head:ordered",
        "part": "head",
        "skills": [
            {"skill_id": "skill:critical-eye", "level": 1},
            {"skill_id": "skill:weakness-exploit", "level": 2},
        ],
        "slots": [
            {"kind": "armor", "level": 1},
            {"kind": "armor", "level": 2},
        ],
    }

    equipment = decode_equipment_definition(value=value)

    assert equipment.skills == (
        SkillContribution("skill:critical-eye", 1),
        SkillContribution("skill:weakness-exploit", 2),
    )
    assert equipment.slots == (
        DecorationSlot(DecorationKind.ARMOR, 1),
        DecorationSlot(DecorationKind.ARMOR, 2),
    )


def test_decode_equipment_definition_preserves_duplicate_slots() -> None:
    value = armor_value()
    value["slots"] = [
        {"kind": "armor", "level": 1},
        {"kind": "armor", "level": 1},
    ]

    equipment = decode_equipment_definition(value=value)

    assert equipment.slots == (
        DecorationSlot(DecorationKind.ARMOR, 1),
        DecorationSlot(DecorationKind.ARMOR, 1),
    )


def test_decode_equipment_definition_accepts_reverse_root_key_order() -> None:
    equipment = decode_equipment_definition(
        value={
            "slots": [{"kind": "weapon", "level": 1}],
            "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
            "part": "weapon",
            "equipment_id": "fixture:weapon:training-blade",
        },
    )

    assert equipment.part is EquipmentPart.WEAPON
    assert equipment.equipment_id == "fixture:weapon:training-blade"


def test_decode_equipment_definition_accepts_custom_path() -> None:
    equipment = decode_equipment_definition(
        value=armor_value(),
        path="$.equipment[0]",
    )

    assert equipment == EquipmentDefinition(
        equipment_id="fixture:head:precision-alpha",
        part=EquipmentPart.HEAD,
        skills=(SkillContribution("skill:critical-eye", 1),),
        slots=(DecorationSlot(DecorationKind.ARMOR, 1),),
    )


def test_decode_equipment_definition_does_not_mutate_nested_input() -> None:
    value = weapon_value()
    original = copy.deepcopy(value)

    decode_equipment_definition(value=value)

    assert value == original


def test_decode_equipment_definition_arguments_are_keyword_only() -> None:
    signature = inspect.signature(decode_equipment_definition)

    assert signature.parameters["value"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["path"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        decode_equipment_definition(weapon_value())  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("part", "slot_kind", "expected_slot_kind"),
    [
        ("weapon", "armor", DecorationKind.ARMOR),
        ("head", "weapon", DecorationKind.WEAPON),
    ],
)
def test_decode_equipment_definition_does_not_validate_part_slot_kind_consistency(
    part: str,
    slot_kind: str,
    expected_slot_kind: DecorationKind,
) -> None:
    value = empty_equipment_value()
    value["part"] = part
    value["slots"] = [{"kind": slot_kind, "level": 1}]

    equipment = decode_equipment_definition(value=value)

    assert equipment.slots == (DecorationSlot(expected_slot_kind, 1),)


@pytest.mark.parametrize("value", [None, "equipment", [], ()])
def test_decode_equipment_definition_rejects_non_dict_objects(value: object) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0]"
    assert "object" in exc_info.value.detail


def test_decode_equipment_definition_rejects_dict_subclass() -> None:
    class EquipmentDict(dict[str, object]):
        pass

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(
            value=EquipmentDict(weapon_value()),
            path="$.equipment[0]",
        )

    assert exc_info.value.path == "$.equipment[0]"
    assert "object" in exc_info.value.detail


@pytest.mark.parametrize(
    ("value", "expected_fragments"),
    [
        (
            {
                "part": "weapon",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
                "slots": [{"kind": "weapon", "level": 1}],
            },
            ("equipment_id",),
        ),
        (
            {
                "equipment_id": "fixture:weapon:training-blade",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
                "slots": [{"kind": "weapon", "level": 1}],
            },
            ("part",),
        ),
        (
            {
                "equipment_id": "fixture:weapon:training-blade",
                "part": "weapon",
                "slots": [{"kind": "weapon", "level": 1}],
            },
            ("skills",),
        ),
        (
            {
                "equipment_id": "fixture:weapon:training-blade",
                "part": "weapon",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
            },
            ("slots",),
        ),
        ({}, ("equipment_id", "part", "skills", "slots")),
        (
            {
                "equipment_id": "fixture:weapon:training-blade",
                "part": "weapon",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
                "slots": [{"kind": "weapon", "level": 1}],
                "extra": True,
            },
            ("extra",),
        ),
        (
            {
                "equipment_id": "fixture:weapon:training-blade",
                "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
                "slots": [{"kind": "weapon", "level": 1}],
                "unexpected": True,
            },
            ("part", "unexpected"),
        ),
    ],
)
def test_decode_equipment_definition_rejects_invalid_root_shape(
    value: dict[object, object],
    expected_fragments: tuple[str, ...],
) -> None:
    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0]"
    for expected_fragment in expected_fragments:
        assert expected_fragment in exc_info.value.detail


def test_decode_equipment_definition_handles_non_string_extra_keys_deterministically() -> (
    None
):
    value = weapon_value()
    value[3] = True
    value[("x",)] = False

    with pytest.raises(CatalogDecodeError) as first_error:
        decode_equipment_definition(value=value, path="$.equipment[0]")
    with pytest.raises(CatalogDecodeError) as second_error:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert first_error.value.path == "$.equipment[0]"
    assert first_error.value.detail == second_error.value.detail
    assert "3" in first_error.value.detail
    assert "x" in first_error.value.detail


@pytest.mark.parametrize(
    ("equipment_id", "expected_cause"),
    [
        (1, TypeError),
        (None, TypeError),
        ("", ValueError),
        (" ", ValueError),
        (" fixture:weapon:training-blade", ValueError),
        ("fixture:weapon:training-blade ", ValueError),
    ],
)
def test_decode_equipment_definition_converts_invalid_equipment_id_errors(
    equipment_id: object,
    expected_cause: type[Exception],
) -> None:
    value = weapon_value()
    value["equipment_id"] = equipment_id

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0]"
    assert "equipment_id" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    ("part", "expected_cause"),
    [
        ("Weapon", ValueError),
        ("body", ValueError),
        ("helm", ValueError),
        ("", ValueError),
        (1, TypeError),
        (None, TypeError),
        (True, TypeError),
        (EquipmentPart.WEAPON, TypeError),
    ],
)
def test_decode_equipment_definition_converts_invalid_part_errors(
    part: object,
    expected_cause: type[Exception],
) -> None:
    value = weapon_value()
    value["part"] = part

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0].part"
    assert "part" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, expected_cause)


@pytest.mark.parametrize(
    "skills",
    [
        ({"skill_id": "skill:attack-boost", "level": 1},),
        {"skill_id": "skill:attack-boost", "level": 1},
        {("skill:attack-boost", 1)},
        skills_generator(),
        None,
    ],
)
def test_decode_equipment_definition_rejects_non_list_skills(skills: object) -> None:
    value = weapon_value()
    value["skills"] = skills

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0].skills"
    assert "skills" in exc_info.value.detail


def test_decode_equipment_definition_rejects_skills_list_subclass() -> None:
    class SkillList(list[object]):
        pass

    value = weapon_value()
    value["skills"] = SkillList([{"skill_id": "skill:attack-boost", "level": 1}])

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0].skills"
    assert "skills" in exc_info.value.detail


@pytest.mark.parametrize(
    ("skills", "expected_path"),
    [
        ([{"level": 1}], "$.equipment[0].skills[0]"),
        (
            [
                {"skill_id": "skill:attack-boost", "level": 1},
                {"skill_id": "skill:critical-eye"},
            ],
            "$.equipment[0].skills[1]",
        ),
        ([{"skill_id": "", "level": 1}], "$.equipment[0].skills[0]"),
    ],
)
def test_decode_equipment_definition_propagates_skill_element_errors(
    skills: list[object],
    expected_path: str,
) -> None:
    value = weapon_value()
    value["skills"] = skills

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == expected_path
    assert_nested_error_not_wrapped(exc_info.value)


@pytest.mark.parametrize(
    "skills",
    [
        [
            {"skill_id": "skill:attack-boost", "level": 1},
            {"skill_id": "skill:attack-boost", "level": 1},
        ],
        [
            {"skill_id": "skill:attack-boost", "level": 1},
            {"skill_id": "skill:attack-boost", "level": 2},
        ],
    ],
)
def test_decode_equipment_definition_converts_duplicate_skill_errors(
    skills: list[dict[str, object]],
) -> None:
    value = weapon_value()
    value["skills"] = skills

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0]"
    assert "skills" in exc_info.value.detail
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "slots",
    [
        ({"kind": "weapon", "level": 1},),
        {"kind": "weapon", "level": 1},
        {("weapon", 1)},
        slots_generator(),
        None,
    ],
)
def test_decode_equipment_definition_rejects_non_list_slots(slots: object) -> None:
    value = weapon_value()
    value["slots"] = slots

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0].slots"
    assert "slots" in exc_info.value.detail


def test_decode_equipment_definition_rejects_slots_list_subclass() -> None:
    class SlotList(list[object]):
        pass

    value = weapon_value()
    value["slots"] = SlotList([{"kind": "weapon", "level": 1}])

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == "$.equipment[0].slots"
    assert "slots" in exc_info.value.detail


@pytest.mark.parametrize(
    ("slots", "expected_path"),
    [
        ([{"level": 1}], "$.equipment[0].slots[0]"),
        (
            [
                {"kind": "weapon", "level": 1},
                {"kind": "armor"},
            ],
            "$.equipment[0].slots[1]",
        ),
        ([{"kind": "body", "level": 1}], "$.equipment[0].slots[0]"),
        ([{"kind": "weapon", "level": 0}], "$.equipment[0].slots[0]"),
    ],
)
def test_decode_equipment_definition_propagates_slot_element_errors(
    slots: list[object],
    expected_path: str,
) -> None:
    value = weapon_value()
    value["slots"] = slots

    with pytest.raises(CatalogDecodeError) as exc_info:
        decode_equipment_definition(value=value, path="$.equipment[0]")

    assert exc_info.value.path == expected_path
    assert_nested_error_not_wrapped(exc_info.value)


def test_existing_skill_contribution_decoder_still_works() -> None:
    contribution = decode_skill_contribution(
        value={"skill_id": "skill:attack-boost", "level": 1},
    )

    assert contribution == SkillContribution("skill:attack-boost", 1)


def test_existing_decoration_slot_decoder_still_works() -> None:
    slot = decode_decoration_slot(value={"kind": "weapon", "level": 1})

    assert slot == DecorationSlot(DecorationKind.WEAPON, 1)


def test_existing_decoration_definition_decoder_still_works() -> None:
    decoration = decode_decoration_definition(
        value={
            "decoration_id": "fixture:decoration:weapon-power-1",
            "required_slot": {"kind": "weapon", "level": 1},
            "skills": [{"skill_id": "skill:attack-boost", "level": 1}],
        },
    )

    assert decoration == DecorationDefinition(
        decoration_id="fixture:decoration:weapon-power-1",
        required_slot=DecorationSlot(DecorationKind.WEAPON, 1),
        skills=(SkillContribution("skill:attack-boost", 1),),
    )


def test_catalog_decode_error_still_imports_directly() -> None:
    error = CatalogDecodeError(path="$.equipment[0]", detail="invalid object")

    assert str(error) == "$.equipment[0]: invalid object"
