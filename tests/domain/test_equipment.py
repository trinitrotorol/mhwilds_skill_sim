from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain import (
    DecorationDefinition,
    DecorationKind,
    DecorationSlot,
    EquipmentDefinition,
    EquipmentPart,
    SkillContribution,
    can_place_decoration,
)


EXPECTED_EQUIPMENT_PARTS = [
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
]

EXPECTED_EQUIPMENT_PART_VALUES = [
    "weapon",
    "head",
    "chest",
    "arms",
    "waist",
    "legs",
    "charm",
]


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def equipment(
    equipment_id: str = "weapon:great-sword:hope-blade",
    part: EquipmentPart = EquipmentPart.WEAPON,
    skills: tuple[SkillContribution, ...] | None = None,
    slots: tuple[DecorationSlot, ...] | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=skills if skills is not None else (skill(),),
        slots=slots if slots is not None else (weapon_slot(1),),
    )


def test_equipment_part_declaration_order_matches_public_contract() -> None:
    assert list(EquipmentPart) == EXPECTED_EQUIPMENT_PARTS


def test_equipment_part_values_match_public_contract() -> None:
    assert [part.value for part in EquipmentPart] == EXPECTED_EQUIPMENT_PART_VALUES


def test_equipment_part_values_are_unique() -> None:
    values = [part.value for part in EquipmentPart]

    assert len(values) == len(set(values))


@pytest.mark.parametrize("value", EXPECTED_EQUIPMENT_PART_VALUES)
def test_equipment_part_can_be_created_from_valid_strings(value: str) -> None:
    assert EquipmentPart(value).value == value


def test_equipment_part_str_is_stable_value() -> None:
    assert str(EquipmentPart.WEAPON) == "weapon"


@pytest.mark.parametrize("value", ["body", "helm", "Weapon", ""])
def test_equipment_part_rejects_undefined_values(value: str) -> None:
    with pytest.raises(ValueError):
        EquipmentPart(value)


def test_domain_package_exports_equipment_part() -> None:
    from mhwilds_skill_sim.domain import EquipmentPart as ExportedEquipmentPart

    assert ExportedEquipmentPart is EquipmentPart


def test_domain_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.domain import (
        DecorationDefinition as ExportedDecorationDefinition,
        DecorationKind as ExportedDecorationKind,
        DecorationSlot as ExportedDecorationSlot,
        SkillContribution as ExportedSkillContribution,
        can_place_decoration as exported_can_place_decoration,
    )

    assert ExportedDecorationDefinition is DecorationDefinition
    assert ExportedDecorationKind is DecorationKind
    assert ExportedDecorationSlot is DecorationSlot
    assert ExportedSkillContribution is SkillContribution
    assert exported_can_place_decoration is can_place_decoration


def test_can_create_weapon_equipment_definition_with_skills_and_slots() -> None:
    definition = EquipmentDefinition(
        equipment_id="weapon:great-sword:hope-blade",
        part=EquipmentPart.WEAPON,
        skills=(skill("skill:attack-boost", 1),),
        slots=(weapon_slot(1), weapon_slot(2)),
    )

    assert definition.equipment_id == "weapon:great-sword:hope-blade"
    assert definition.part is EquipmentPart.WEAPON
    assert definition.skills == (skill("skill:attack-boost", 1),)
    assert definition.slots == (weapon_slot(1), weapon_slot(2))


def test_can_create_armor_equipment_definition_with_skills_and_slots() -> None:
    definition = EquipmentDefinition(
        equipment_id="armor:head:hope-mask",
        part=EquipmentPart.HEAD,
        skills=(skill("skill:critical-eye", 1),),
        slots=(armor_slot(2),),
    )

    assert definition.equipment_id == "armor:head:hope-mask"
    assert definition.part is EquipmentPart.HEAD
    assert definition.skills == (skill("skill:critical-eye", 1),)
    assert definition.slots == (armor_slot(2),)


def test_can_create_equipment_definition_without_skills_or_slots() -> None:
    definition = equipment(skills=(), slots=())

    assert definition.skills == ()
    assert definition.slots == ()


@pytest.mark.parametrize("part", EXPECTED_EQUIPMENT_PARTS)
def test_can_create_equipment_definition_for_every_part(part: EquipmentPart) -> None:
    definition = equipment(part=part)

    assert definition.part is part


@pytest.mark.parametrize(
    "equipment_id",
    [
        "weapon:great-sword:hope-blade",
        "armor:head:hope-mask",
        "charm:challenger-1",
        "wilds:equipment:-2144349312",
        "Equipment:Internal_ID-01",
    ],
)
def test_equipment_definition_preserves_equipment_id_without_normalization(
    equipment_id: str,
) -> None:
    definition = equipment(equipment_id=equipment_id)

    assert definition.equipment_id == equipment_id


def test_equipment_definition_preserves_skill_order() -> None:
    skills = (
        skill("skill:attack-boost", 1),
        skill("skill:critical-eye", 2),
    )

    definition = equipment(skills=skills)

    assert definition.skills == skills


def test_equipment_definition_preserves_slot_order() -> None:
    slots = (armor_slot(1), armor_slot(3), armor_slot(2))

    definition = equipment(slots=slots)

    assert definition.slots == slots


def test_equipment_definitions_with_same_values_are_equal() -> None:
    assert equipment() == equipment()


@pytest.mark.parametrize(
    "other",
    [
        equipment(equipment_id="weapon:great-sword:other"),
        equipment(part=EquipmentPart.HEAD),
        equipment(skills=(skill("skill:critical-eye", 1),)),
        equipment(slots=(weapon_slot(2),)),
    ],
)
def test_equipment_definitions_with_different_values_are_not_equal(
    other: EquipmentDefinition,
) -> None:
    assert equipment() != other


def test_equipment_definition_is_hashable() -> None:
    assert hash(equipment()) == hash(equipment())


def test_equipment_definition_fields_cannot_be_reassigned() -> None:
    definition = equipment()

    with pytest.raises(FrozenInstanceError):
        definition.equipment_id = "weapon:great-sword:other"


@pytest.mark.parametrize("equipment_id", ["", " ", "\t\n"])
def test_equipment_definition_rejects_empty_or_blank_equipment_id(
    equipment_id: str,
) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        equipment(equipment_id=equipment_id)


@pytest.mark.parametrize(
    "equipment_id",
    [" weapon:great-sword:hope-blade", "\tweapon:great-sword:hope-blade"],
)
def test_equipment_definition_rejects_leading_whitespace_equipment_id(
    equipment_id: str,
) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        equipment(equipment_id=equipment_id)


@pytest.mark.parametrize(
    "equipment_id",
    ["weapon:great-sword:hope-blade ", "weapon:great-sword:hope-blade\n"],
)
def test_equipment_definition_rejects_trailing_whitespace_equipment_id(
    equipment_id: str,
) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        equipment(equipment_id=equipment_id)


@pytest.mark.parametrize("equipment_id", [1, None])
def test_equipment_definition_rejects_non_str_equipment_id(
    equipment_id: object,
) -> None:
    with pytest.raises(TypeError, match="equipment_id"):
        equipment(equipment_id=equipment_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("part", ["weapon", None])
def test_equipment_definition_rejects_invalid_part(part: object) -> None:
    with pytest.raises(TypeError, match="part"):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=part,  # type: ignore[arg-type]
            skills=(skill(),),
            slots=(weapon_slot(1),),
        )


def test_equipment_definition_accepts_empty_skills() -> None:
    definition = equipment(skills=())

    assert definition.skills == ()


def skill_generator() -> Iterator[SkillContribution]:
    yield skill()


@pytest.mark.parametrize(
    "skills",
    [
        [skill()],
        {skill()},
        skill_generator(),
    ],
)
def test_equipment_definition_rejects_non_tuple_skills(skills: object) -> None:
    with pytest.raises(TypeError, match="skills"):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=EquipmentPart.WEAPON,
            skills=skills,  # type: ignore[arg-type]
            slots=(weapon_slot(1),),
        )


@pytest.mark.parametrize("invalid_skill", ["skill:attack-boost", None])
def test_equipment_definition_rejects_invalid_skill_elements(
    invalid_skill: object,
) -> None:
    with pytest.raises(TypeError, match="skills"):
        equipment(skills=(invalid_skill,))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "skills",
    [
        (
            skill("skill:attack-boost", 1),
            skill("skill:attack-boost", 1),
        ),
        (
            skill("skill:attack-boost", 1),
            skill("skill:attack-boost", 2),
        ),
    ],
)
def test_equipment_definition_rejects_duplicate_skill_ids(
    skills: tuple[SkillContribution, ...],
) -> None:
    with pytest.raises(ValueError, match="skills"):
        equipment(skills=skills)


def test_equipment_definition_accepts_multiple_different_skill_ids() -> None:
    skills = (
        skill("skill:attack-boost", 1),
        skill("skill:critical-eye", 1),
    )

    definition = equipment(skills=skills)

    assert definition.skills == skills


def test_equipment_definition_accepts_empty_slots() -> None:
    definition = equipment(slots=())

    assert definition.slots == ()


def slot_generator() -> Iterator[DecorationSlot]:
    yield weapon_slot(1)


@pytest.mark.parametrize(
    "slots",
    [
        [weapon_slot(1)],
        {weapon_slot(1)},
        slot_generator(),
    ],
)
def test_equipment_definition_rejects_non_tuple_slots(slots: object) -> None:
    with pytest.raises(TypeError, match="slots"):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=EquipmentPart.WEAPON,
            skills=(skill(),),
            slots=slots,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_slot", ["weapon", None])
def test_equipment_definition_rejects_invalid_slot_elements(
    invalid_slot: object,
) -> None:
    with pytest.raises(TypeError, match="slots"):
        equipment(slots=(invalid_slot,))  # type: ignore[arg-type]


def test_equipment_definition_accepts_duplicate_slots_and_preserves_them() -> None:
    duplicate_slot = weapon_slot(1)
    slots = (duplicate_slot, weapon_slot(2), duplicate_slot)

    definition = equipment(slots=slots)

    assert definition.slots == slots
    assert len(definition.slots) == 3


def test_domain_package_exports_equipment_definition() -> None:
    from mhwilds_skill_sim.domain import (
        EquipmentDefinition as ExportedEquipmentDefinition,
    )

    assert ExportedEquipmentDefinition is EquipmentDefinition


def test_domain_package_keeps_existing_public_exports_with_equipment_definition() -> (
    None
):
    from mhwilds_skill_sim.domain import (
        DecorationDefinition as ExportedDecorationDefinition,
        DecorationKind as ExportedDecorationKind,
        DecorationSlot as ExportedDecorationSlot,
        EquipmentPart as ExportedEquipmentPart,
        SkillContribution as ExportedSkillContribution,
        can_place_decoration as exported_can_place_decoration,
    )

    assert ExportedDecorationDefinition is DecorationDefinition
    assert ExportedDecorationKind is DecorationKind
    assert ExportedDecorationSlot is DecorationSlot
    assert ExportedEquipmentPart is EquipmentPart
    assert ExportedSkillContribution is SkillContribution
    assert exported_can_place_decoration is can_place_decoration
