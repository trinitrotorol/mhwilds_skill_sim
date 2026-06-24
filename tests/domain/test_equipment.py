from __future__ import annotations

import pytest

from mhwilds_skill_sim.domain import (
    DecorationDefinition,
    DecorationKind,
    DecorationSlot,
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
