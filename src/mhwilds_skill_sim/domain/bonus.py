"""Equipment bonus skill activation rules."""

from __future__ import annotations

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
)


def calculate_equipment_bonus_skill_contributions(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    skill_definitions: tuple[SkillDefinition, ...],
) -> tuple[SkillContribution, ...]:
    if type(equipment) is not tuple:
        raise TypeError("equipment must be tuple")

    for definition in equipment:
        if not isinstance(definition, EquipmentDefinition):
            raise TypeError("equipment must contain only EquipmentDefinition")

    if type(skill_definitions) is not tuple:
        raise TypeError("skill_definitions must be tuple")

    definitions_by_id: dict[str, SkillDefinition] = {}
    for definition in skill_definitions:
        if not isinstance(definition, SkillDefinition):
            raise TypeError("skill_definitions must contain only SkillDefinition")

        if definition.skill_id in definitions_by_id:
            raise ValueError("skill_definitions must not contain duplicate skill_id")

        definitions_by_id[definition.skill_id] = definition

    series_piece_counts: dict[str, int] = {}
    group_piece_counts: dict[str, int] = {}
    for definition in equipment:
        if definition.series_skill_id is not None:
            series_skill = definitions_by_id.get(definition.series_skill_id)
            if series_skill is None:
                raise ValueError(
                    "equipment series_skill_id must reference skill_definitions"
                )
            if series_skill.kind is not SkillKind.SERIES:
                raise ValueError(
                    "equipment series_skill_id must reference a series skill in "
                    "skill_definitions"
                )
            series_piece_counts[definition.series_skill_id] = (
                series_piece_counts.get(definition.series_skill_id, 0) + 1
            )

        if definition.group_skill_id is not None:
            group_skill = definitions_by_id.get(definition.group_skill_id)
            if group_skill is None:
                raise ValueError(
                    "equipment group_skill_id must reference skill_definitions"
                )
            if group_skill.kind is not SkillKind.GROUP:
                raise ValueError(
                    "equipment group_skill_id must reference a group skill in "
                    "skill_definitions"
                )
            group_piece_counts[definition.group_skill_id] = (
                group_piece_counts.get(definition.group_skill_id, 0) + 1
            )

    contributions: list[SkillContribution] = []
    for definition in skill_definitions:
        if definition.kind is SkillKind.SERIES:
            piece_count = series_piece_counts.get(definition.skill_id, 0)
        elif definition.kind is SkillKind.GROUP:
            piece_count = group_piece_counts.get(definition.skill_id, 0)
        else:
            continue

        activated_level: int | None = None
        for rank in definition.ranks:
            if rank.required_pieces is not None and rank.required_pieces <= piece_count:
                activated_level = rank.level

        if activated_level is not None:
            contributions.append(
                SkillContribution(
                    skill_id=definition.skill_id,
                    level=activated_level,
                )
            )

    return tuple(contributions)
