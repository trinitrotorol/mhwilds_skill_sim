from __future__ import annotations

import pytest

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.validation.decoration import (
    can_place_decoration_in_equipment_slot,
)


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def equipment(
    *,
    part: EquipmentPart = EquipmentPart.WEAPON,
    slots: tuple[DecorationSlot, ...] | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id="equipment:test",
        part=part,
        skills=(skill(),),
        slots=slots if slots is not None else (weapon_slot(1),),
    )


def decoration(
    *,
    required_slot: DecorationSlot | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id="decoration:test",
        required_slot=required_slot or weapon_slot(1),
        skills=(skill(),),
    )


@pytest.mark.parametrize(
    ("required_slot", "available_slot"),
    [
        (weapon_slot(1), weapon_slot(1)),
        (weapon_slot(1), weapon_slot(2)),
        (armor_slot(1), armor_slot(1)),
        (armor_slot(2), armor_slot(4)),
    ],
)
def test_can_place_matching_decoration_in_large_enough_slot(
    required_slot: DecorationSlot,
    available_slot: DecorationSlot,
) -> None:
    assert can_place_decoration_in_equipment_slot(
        equipment=equipment(slots=(available_slot,)),
        decoration=decoration(required_slot=required_slot),
        slot_index=0,
    )


def test_uses_specified_slot_index() -> None:
    assert can_place_decoration_in_equipment_slot(
        equipment=equipment(slots=(armor_slot(1), weapon_slot(1))),
        decoration=decoration(required_slot=weapon_slot(1)),
        slot_index=1,
    )


def test_can_reject_one_index_and_accept_another() -> None:
    test_equipment = equipment(slots=(armor_slot(1), weapon_slot(1)))
    test_decoration = decoration(required_slot=weapon_slot(1))

    assert not can_place_decoration_in_equipment_slot(
        equipment=test_equipment,
        decoration=test_decoration,
        slot_index=0,
    )
    assert can_place_decoration_in_equipment_slot(
        equipment=test_equipment,
        decoration=test_decoration,
        slot_index=1,
    )


@pytest.mark.parametrize("slot_index", [0, 1])
def test_duplicate_identical_slots_are_checked_by_specified_index(
    slot_index: int,
) -> None:
    assert can_place_decoration_in_equipment_slot(
        equipment=equipment(slots=(weapon_slot(1), weapon_slot(1))),
        decoration=decoration(required_slot=weapon_slot(1)),
        slot_index=slot_index,
    )


def test_weapon_part_with_armor_slot_can_accept_armor_decoration() -> None:
    assert can_place_decoration_in_equipment_slot(
        equipment=equipment(part=EquipmentPart.WEAPON, slots=(armor_slot(1),)),
        decoration=decoration(required_slot=armor_slot(1)),
        slot_index=0,
    )


def test_head_part_with_weapon_slot_can_accept_weapon_decoration() -> None:
    assert can_place_decoration_in_equipment_slot(
        equipment=equipment(part=EquipmentPart.HEAD, slots=(weapon_slot(1),)),
        decoration=decoration(required_slot=weapon_slot(1)),
        slot_index=0,
    )


def test_requires_keyword_arguments() -> None:
    with pytest.raises(TypeError):
        can_place_decoration_in_equipment_slot(  # type: ignore[misc]
            equipment(slots=(weapon_slot(1),)),
            decoration(required_slot=weapon_slot(1)),
            0,
        )


def test_validation_package_exports_public_function() -> None:
    from mhwilds_skill_sim.validation import (
        can_place_decoration_in_equipment_slot as exported_function,
    )

    assert exported_function is can_place_decoration_in_equipment_slot


@pytest.mark.parametrize(
    ("required_slot", "available_slot"),
    [
        (weapon_slot(2), weapon_slot(1)),
        (armor_slot(4), armor_slot(3)),
        (weapon_slot(1), armor_slot(1)),
        (armor_slot(1), weapon_slot(1)),
    ],
)
def test_rejects_incompatible_slots(
    required_slot: DecorationSlot,
    available_slot: DecorationSlot,
) -> None:
    assert not can_place_decoration_in_equipment_slot(
        equipment=equipment(slots=(available_slot,)),
        decoration=decoration(required_slot=required_slot),
        slot_index=0,
    )


@pytest.mark.parametrize("slot_index", [-1, 1, 2])
def test_returns_false_when_slot_index_does_not_exist(slot_index: int) -> None:
    assert not can_place_decoration_in_equipment_slot(
        equipment=equipment(slots=(weapon_slot(1),)),
        decoration=decoration(required_slot=weapon_slot(1)),
        slot_index=slot_index,
    )


def test_returns_false_when_equipment_has_no_slots() -> None:
    assert not can_place_decoration_in_equipment_slot(
        equipment=equipment(slots=()),
        decoration=decoration(required_slot=weapon_slot(1)),
        slot_index=0,
    )


@pytest.mark.parametrize("invalid_equipment", ["equipment:test", None])
def test_rejects_invalid_equipment(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        can_place_decoration_in_equipment_slot(
            equipment=invalid_equipment,  # type: ignore[arg-type]
            decoration=decoration(required_slot=weapon_slot(1)),
            slot_index=0,
        )


@pytest.mark.parametrize("invalid_decoration", ["decoration:test", None])
def test_rejects_invalid_decoration(invalid_decoration: object) -> None:
    with pytest.raises(TypeError, match="decoration"):
        can_place_decoration_in_equipment_slot(
            equipment=equipment(slots=(weapon_slot(1),)),
            decoration=invalid_decoration,  # type: ignore[arg-type]
            slot_index=0,
        )


@pytest.mark.parametrize("invalid_slot_index", [True, 1.0, "0", None])
def test_rejects_invalid_slot_index(invalid_slot_index: object) -> None:
    with pytest.raises(TypeError, match="slot_index"):
        can_place_decoration_in_equipment_slot(
            equipment=equipment(slots=(weapon_slot(1),)),
            decoration=decoration(required_slot=weapon_slot(1)),
            slot_index=invalid_slot_index,  # type: ignore[arg-type]
        )
