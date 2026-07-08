"""Decoration placement list validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.validation.decoration import (
    can_place_decoration_in_equipment_slot,
)
from mhwilds_skill_sim.validation.placement import DecorationPlacement


class DecorationPlacementIssueCode(StrEnum):
    UNKNOWN_EQUIPMENT = "unknown_equipment"
    UNKNOWN_DECORATION = "unknown_decoration"
    INVALID_SLOT_INDEX = "invalid_slot_index"
    DUPLICATE_SLOT = "duplicate_slot"
    INCOMPATIBLE_SLOT = "incompatible_slot"


@dataclass(frozen=True, slots=True)
class DecorationPlacementIssue:
    placement_index: int
    code: DecorationPlacementIssueCode

    def __post_init__(self) -> None:
        if type(self.placement_index) is not int:
            raise TypeError("placement_index must be int")

        if self.placement_index < 0:
            raise ValueError("placement_index must be at least 0")

        if not isinstance(self.code, DecorationPlacementIssueCode):
            raise TypeError("code must be DecorationPlacementIssueCode")


def validate_decoration_placements(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
    placements: tuple[DecorationPlacement, ...],
) -> tuple[DecorationPlacementIssue, ...]:
    if type(equipment) is not tuple:
        raise TypeError("equipment must be tuple")

    if type(decorations) is not tuple:
        raise TypeError("decorations must be tuple")

    if type(placements) is not tuple:
        raise TypeError("placements must be tuple")

    equipment_by_id: dict[str, EquipmentDefinition] = {}
    for definition in equipment:
        if not isinstance(definition, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")

        if definition.equipment_id in equipment_by_id:
            raise ValueError("equipment must not contain duplicate equipment_id")

        equipment_by_id[definition.equipment_id] = definition

    decorations_by_id: dict[str, DecorationDefinition] = {}
    for definition in decorations:
        if not isinstance(definition, DecorationDefinition):
            raise TypeError("decorations must contain only DecorationDefinition")

        if definition.decoration_id in decorations_by_id:
            raise ValueError("decorations must not contain duplicate decoration_id")

        decorations_by_id[definition.decoration_id] = definition

    for placement in placements:
        if not isinstance(placement, DecorationPlacement):
            raise TypeError("placements must contain only DecorationPlacement")

    issues: list[DecorationPlacementIssue] = []
    used_slots: set[tuple[str, int]] = set()

    for placement_index, placement in enumerate(placements):
        target_equipment = equipment_by_id.get(placement.equipment_id)
        if target_equipment is None:
            issues.append(
                DecorationPlacementIssue(
                    placement_index=placement_index,
                    code=DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT,
                ),
            )
            continue

        target_decoration = decorations_by_id.get(placement.decoration_id)
        if target_decoration is None:
            issues.append(
                DecorationPlacementIssue(
                    placement_index=placement_index,
                    code=DecorationPlacementIssueCode.UNKNOWN_DECORATION,
                ),
            )
            continue

        if placement.slot_index >= len(target_equipment.slots):
            issues.append(
                DecorationPlacementIssue(
                    placement_index=placement_index,
                    code=DecorationPlacementIssueCode.INVALID_SLOT_INDEX,
                ),
            )
            continue

        slot_key = (placement.equipment_id, placement.slot_index)
        if slot_key in used_slots:
            issues.append(
                DecorationPlacementIssue(
                    placement_index=placement_index,
                    code=DecorationPlacementIssueCode.DUPLICATE_SLOT,
                ),
            )
            continue

        if not can_place_decoration_in_equipment_slot(
            equipment=target_equipment,
            decoration=target_decoration,
            slot_index=placement.slot_index,
        ):
            issues.append(
                DecorationPlacementIssue(
                    placement_index=placement_index,
                    code=DecorationPlacementIssueCode.INCOMPATIBLE_SLOT,
                ),
            )
            continue

        used_slots.add(slot_key)

    return tuple(issues)
