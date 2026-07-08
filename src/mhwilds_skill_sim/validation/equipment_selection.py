"""Equipment selection part validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart


class EquipmentSelectionIssueCode(StrEnum):
    MISSING_PART = "missing_part"
    DUPLICATE_PART = "duplicate_part"


@dataclass(frozen=True, slots=True)
class EquipmentSelectionIssue:
    code: EquipmentSelectionIssueCode
    part: EquipmentPart
    equipment_index: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.code, EquipmentSelectionIssueCode):
            raise TypeError("code must be EquipmentSelectionIssueCode")

        if not isinstance(self.part, EquipmentPart):
            raise TypeError("part must be EquipmentPart")

        if self.equipment_index is not None and type(self.equipment_index) is not int:
            raise TypeError("equipment_index must be int or None")

        if self.equipment_index is not None and self.equipment_index < 0:
            raise ValueError("equipment_index must be at least 0")

        if (
            self.code is EquipmentSelectionIssueCode.MISSING_PART
            and self.equipment_index is not None
        ):
            raise ValueError("equipment_index must be None for missing part")

        if (
            self.code is EquipmentSelectionIssueCode.DUPLICATE_PART
            and type(self.equipment_index) is not int
        ):
            raise ValueError("equipment_index must be int for duplicate part")


REQUIRED_EQUIPMENT_PARTS = (
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
)


def validate_equipment_selection(
    *,
    equipment: tuple[EquipmentDefinition, ...],
) -> tuple[EquipmentSelectionIssue, ...]:
    if type(equipment) is not tuple:
        raise TypeError("equipment must be tuple")

    for definition in equipment:
        if not isinstance(definition, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")

    issues: list[EquipmentSelectionIssue] = []
    seen_parts: set[EquipmentPart] = set()

    for equipment_index, definition in enumerate(equipment):
        if definition.part in seen_parts:
            issues.append(
                EquipmentSelectionIssue(
                    code=EquipmentSelectionIssueCode.DUPLICATE_PART,
                    part=definition.part,
                    equipment_index=equipment_index,
                ),
            )
            continue

        seen_parts.add(definition.part)

    for part in REQUIRED_EQUIPMENT_PARTS:
        if part not in seen_parts:
            issues.append(
                EquipmentSelectionIssue(
                    code=EquipmentSelectionIssueCode.MISSING_PART,
                    part=part,
                    equipment_index=None,
                ),
            )

    return tuple(issues)
