"""Build validation facade."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.validation.equipment_selection import (
    EquipmentSelectionIssue,
    validate_equipment_selection,
)
from mhwilds_skill_sim.validation.placement import DecorationPlacement
from mhwilds_skill_sim.validation.placement_validation import (
    DecorationPlacementIssue,
    validate_decoration_placements,
)


@dataclass(frozen=True, slots=True)
class BuildValidationResult:
    equipment_selection_issues: tuple[EquipmentSelectionIssue, ...]
    decoration_placement_issues: tuple[DecorationPlacementIssue, ...]

    def __post_init__(self) -> None:
        if type(self.equipment_selection_issues) is not tuple:
            raise TypeError("equipment_selection_issues must be tuple")

        for issue in self.equipment_selection_issues:
            if not isinstance(issue, EquipmentSelectionIssue):
                raise TypeError(
                    "equipment_selection_issues must contain only "
                    "EquipmentSelectionIssue",
                )

        if type(self.decoration_placement_issues) is not tuple:
            raise TypeError("decoration_placement_issues must be tuple")

        for issue in self.decoration_placement_issues:
            if not isinstance(issue, DecorationPlacementIssue):
                raise TypeError(
                    "decoration_placement_issues must contain only "
                    "DecorationPlacementIssue",
                )


def validate_build(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
    placements: tuple[DecorationPlacement, ...],
) -> BuildValidationResult:
    equipment_selection_issues = validate_equipment_selection(equipment=equipment)
    decoration_placement_issues = validate_decoration_placements(
        equipment=equipment,
        decorations=decorations,
        placements=placements,
    )

    return BuildValidationResult(
        equipment_selection_issues=equipment_selection_issues,
        decoration_placement_issues=decoration_placement_issues,
    )
