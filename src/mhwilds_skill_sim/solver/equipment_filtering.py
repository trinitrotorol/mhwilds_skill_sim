"""Equipment candidate filtering."""

from __future__ import annotations

from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)


def filter_equipment_candidates_by_weapon_kind(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    weapon_kind: WeaponKind | None,
) -> tuple[EquipmentDefinition, ...]:
    if type(equipment) is not tuple:
        raise TypeError("equipment must be tuple")

    seen_equipment_ids: set[str] = set()
    for equipment_item in equipment:
        if not isinstance(equipment_item, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")

        if equipment_item.equipment_id in seen_equipment_ids:
            raise ValueError("equipment must not contain duplicate equipment_id")

        seen_equipment_ids.add(equipment_item.equipment_id)

    if weapon_kind is not None and not isinstance(weapon_kind, WeaponKind):
        raise TypeError("weapon_kind must be WeaponKind or None")

    return tuple(
        equipment_item
        for equipment_item in equipment
        if (
            weapon_kind is None
            or equipment_item.part is not EquipmentPart.WEAPON
            or equipment_item.weapon_kind is weapon_kind
        )
    )
