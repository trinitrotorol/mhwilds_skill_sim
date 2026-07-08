"""Equipment selection enumeration."""

from __future__ import annotations

from itertools import product

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart


REQUIRED_EQUIPMENT_PARTS = (
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
)


def enumerate_equipment_selections(
    *,
    equipment: tuple[EquipmentDefinition, ...],
) -> tuple[tuple[EquipmentDefinition, ...], ...]:
    if type(equipment) is not tuple:
        raise TypeError("equipment must be tuple")

    grouped: dict[EquipmentPart, list[EquipmentDefinition]] = {
        part: [] for part in REQUIRED_EQUIPMENT_PARTS
    }
    for definition in equipment:
        if not isinstance(definition, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")

        grouped[definition.part].append(definition)

    groups = tuple(tuple(grouped[part]) for part in REQUIRED_EQUIPMENT_PARTS)
    if any(not group for group in groups):
        return ()

    return tuple(product(*groups))
