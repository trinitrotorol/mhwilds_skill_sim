"""Equipment bonus skill variant expansion."""

from __future__ import annotations

from dataclasses import replace

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind


def expand_equipment_bonus_skill_variants(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    skill_definitions: tuple[SkillDefinition, ...],
) -> tuple[EquipmentDefinition, ...]:
    if type(equipment) is not tuple:
        raise TypeError("equipment must be tuple")

    seen_equipment_ids: set[str] = set()
    for definition in equipment:
        if not isinstance(definition, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")

        if definition.equipment_id in seen_equipment_ids:
            raise ValueError("equipment must not contain duplicate equipment_id")

        seen_equipment_ids.add(definition.equipment_id)

    if type(skill_definitions) is not tuple:
        raise TypeError("skill_definitions must be tuple")

    seen_skill_ids: set[str] = set()
    for definition in skill_definitions:
        if not isinstance(definition, SkillDefinition):
            raise TypeError("skill_definitions must contain only SkillDefinition")

        if definition.skill_id in seen_skill_ids:
            raise ValueError("skill_definitions must not contain duplicate skill_id")

        seen_skill_ids.add(definition.skill_id)

    series_options = tuple(
        definition.skill_id
        for definition in skill_definitions
        if definition.kind is SkillKind.SERIES
    )
    group_options = tuple(
        definition.skill_id
        for definition in skill_definitions
        if definition.kind is SkillKind.GROUP
    )

    expanded: list[EquipmentDefinition] = []
    for definition in equipment:
        if not (
            definition.allows_series_skill_assignment
            or definition.allows_group_skill_assignment
        ):
            expanded.append(definition)
            continue

        if definition.allows_series_skill_assignment:
            if not series_options:
                raise ValueError(
                    "skill_definitions must contain an option for "
                    "allows_series_skill_assignment"
                )
            selected_series_ids: tuple[str | None, ...] = series_options
        else:
            selected_series_ids = (definition.series_skill_id,)

        if definition.allows_group_skill_assignment:
            if not group_options:
                raise ValueError(
                    "skill_definitions must contain an option for "
                    "allows_group_skill_assignment"
                )
            selected_group_ids: tuple[str | None, ...] = group_options
        else:
            selected_group_ids = (definition.group_skill_id,)

        for series_skill_id in selected_series_ids:
            for group_skill_id in selected_group_ids:
                expanded.append(
                    replace(
                        definition,
                        series_skill_id=series_skill_id,
                        group_skill_id=group_skill_id,
                        allows_series_skill_assignment=False,
                        allows_group_skill_assignment=False,
                    )
                )

    return tuple(expanded)
