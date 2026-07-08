"""Decoration placement validation."""

from __future__ import annotations

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.domain.slot import can_place_decoration


def can_place_decoration_in_equipment_slot(
    *,
    equipment: EquipmentDefinition,
    decoration: DecorationDefinition,
    slot_index: int,
) -> bool:
    if not isinstance(equipment, EquipmentDefinition):
        raise TypeError("equipment must be EquipmentDefinition")

    if not isinstance(decoration, DecorationDefinition):
        raise TypeError("decoration must be DecorationDefinition")

    if type(slot_index) is not int:
        raise TypeError("slot_index must be int")

    if slot_index < 0 or slot_index >= len(equipment.slots):
        return False

    return can_place_decoration(
        required_slot=decoration.required_slot,
        available_slot=equipment.slots[slot_index],
    )
