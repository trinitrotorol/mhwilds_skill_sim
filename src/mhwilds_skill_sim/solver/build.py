"""Build candidate enumeration."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.domain.skill import SkillDefinition
from mhwilds_skill_sim.solver.decoration import (
    enumerate_decoration_placement_combinations,
)
from mhwilds_skill_sim.solver.equipment import enumerate_equipment_selections
from mhwilds_skill_sim.solver.equipment_variants import (
    expand_equipment_bonus_skill_variants,
)
from mhwilds_skill_sim.validation.build import aggregate_valid_build_skill_levels
from mhwilds_skill_sim.validation.placement import DecorationPlacement


@dataclass(frozen=True, slots=True)
class BuildCandidate:
    equipment: tuple[EquipmentDefinition, ...]
    placements: tuple[DecorationPlacement, ...]
    skill_levels: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _validate_equipment(value=self.equipment)
        _validate_placements(value=self.placements)
        _validate_skill_levels(value=self.skill_levels)


def enumerate_build_candidates(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
    skill_definitions: tuple[SkillDefinition, ...] = (),
) -> tuple[BuildCandidate, ...]:
    _validate_equipment(value=equipment)
    _validate_decorations(value=decorations)
    _validate_skill_definitions(value=skill_definitions)
    _validate_unique_equipment_ids(equipment=equipment)
    _validate_unique_decoration_ids(decorations=decorations)

    expanded_equipment = expand_equipment_bonus_skill_variants(
        equipment=equipment,
        skill_definitions=skill_definitions,
    )

    candidates: list[BuildCandidate] = []
    for selection in enumerate_equipment_selections(equipment=expanded_equipment):
        for placements in enumerate_decoration_placement_combinations(
            equipment=selection,
            decorations=decorations,
        ):
            skill_levels = aggregate_valid_build_skill_levels(
                equipment=selection,
                decorations=decorations,
                placements=placements,
                skill_definitions=skill_definitions,
            )
            candidates.append(
                BuildCandidate(
                    equipment=selection,
                    placements=placements,
                    skill_levels=tuple(skill_levels.items()),
                ),
            )

    return tuple(candidates)


def _validate_equipment(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("equipment must be tuple")

    for definition in value:
        if not isinstance(definition, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")


def _validate_decorations(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("decorations must be tuple")

    for definition in value:
        if not isinstance(definition, DecorationDefinition):
            raise TypeError("decorations must contain only DecorationDefinition")


def _validate_skill_definitions(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("skill_definitions must be tuple")

    seen_skill_ids: set[str] = set()
    for definition in value:
        if not isinstance(definition, SkillDefinition):
            raise TypeError("skill_definitions must contain only SkillDefinition")

        if definition.skill_id in seen_skill_ids:
            raise ValueError("skill_definitions must not contain duplicate skill_id")

        seen_skill_ids.add(definition.skill_id)


def _validate_placements(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("placements must be tuple")

    for placement in value:
        if not isinstance(placement, DecorationPlacement):
            raise TypeError("placements must contain only DecorationPlacement")


def _validate_skill_levels(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("skill_levels must be tuple")

    seen_skill_ids: set[str] = set()
    for skill_level in value:
        if type(skill_level) is not tuple:
            raise TypeError("skill_levels must contain only tuple entries")

        if len(skill_level) != 2:
            raise ValueError("skill_levels entries must have length 2")

        skill_id, total_level = skill_level
        _validate_skill_id(value=skill_id)
        _validate_total_level(value=total_level)

        if skill_id in seen_skill_ids:
            raise ValueError("skill_levels must not contain duplicate skill_id")

        seen_skill_ids.add(skill_id)


def _validate_skill_id(*, value: object) -> None:
    if type(value) is not str:
        raise TypeError("skill_levels skill_id must be str")

    if value == "":
        raise ValueError("skill_levels skill_id must not be empty")

    if value.strip() == "":
        raise ValueError("skill_levels skill_id must not be blank")

    if value != value.strip():
        raise ValueError(
            "skill_levels skill_id must not have leading or trailing whitespace",
        )


def _validate_total_level(*, value: object) -> None:
    if type(value) is not int:
        raise TypeError("skill_levels total level must be int")

    if value < 0:
        raise ValueError("skill_levels total level must be at least 0")


def _validate_unique_equipment_ids(
    *,
    equipment: tuple[EquipmentDefinition, ...],
) -> None:
    seen_equipment_ids: set[str] = set()
    for definition in equipment:
        if definition.equipment_id in seen_equipment_ids:
            raise ValueError("equipment must not contain duplicate equipment_id")

        seen_equipment_ids.add(definition.equipment_id)


def _validate_unique_decoration_ids(
    *,
    decorations: tuple[DecorationDefinition, ...],
) -> None:
    seen_decoration_ids: set[str] = set()
    for definition in decorations:
        if definition.decoration_id in seen_decoration_ids:
            raise ValueError("decorations must not contain duplicate decoration_id")

        seen_decoration_ids.add(definition.decoration_id)
