"""Decoration placement combination enumeration."""

from __future__ import annotations

from itertools import product

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.validation.decoration import (
    can_place_decoration_in_equipment_slot,
)
from mhwilds_skill_sim.validation.placement import DecorationPlacement


def enumerate_decoration_placement_combinations(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
) -> tuple[tuple[DecorationPlacement, ...], ...]:
    if type(equipment) is not tuple:
        raise TypeError("equipment must be tuple")

    if type(decorations) is not tuple:
        raise TypeError("decorations must be tuple")

    seen_equipment_ids: set[str] = set()
    for definition in equipment:
        if not isinstance(definition, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")

        if definition.equipment_id in seen_equipment_ids:
            raise ValueError("equipment must not contain duplicate equipment_id")

        seen_equipment_ids.add(definition.equipment_id)

    seen_decoration_ids: set[str] = set()
    for decoration in decorations:
        if not isinstance(decoration, DecorationDefinition):
            raise TypeError("decorations must contain only DecorationDefinition")

        if decoration.decoration_id in seen_decoration_ids:
            raise ValueError("decorations must not contain duplicate decoration_id")

        seen_decoration_ids.add(decoration.decoration_id)

    slot_options: list[tuple[DecorationPlacement | None, ...]] = []
    for definition in equipment:
        for slot_index, _slot in enumerate(definition.slots):
            options: list[DecorationPlacement | None] = [None]
            for decoration in decorations:
                if can_place_decoration_in_equipment_slot(
                    equipment=definition,
                    decoration=decoration,
                    slot_index=slot_index,
                ):
                    options.append(
                        DecorationPlacement(
                            equipment_id=definition.equipment_id,
                            slot_index=slot_index,
                            decoration_id=decoration.decoration_id,
                        ),
                    )
            slot_options.append(tuple(options))

    combinations: list[tuple[DecorationPlacement, ...]] = []
    for choices in product(*slot_options):
        combinations.append(tuple(choice for choice in choices if choice is not None))

    return tuple(combinations)
