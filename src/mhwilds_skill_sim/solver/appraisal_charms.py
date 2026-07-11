"""Theoretical appraisal charm equipment generation."""

from __future__ import annotations

from itertools import product

from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
)
from mhwilds_skill_sim.domain.slot import DecorationSlot


def generate_appraisal_charm_equipment_candidates(
    *,
    skill_groups: tuple[AppraisalCharmSkillGroupDefinition, ...],
    patterns: tuple[AppraisalCharmPatternDefinition, ...],
    skill_definitions: tuple[SkillDefinition, ...],
) -> tuple[EquipmentDefinition, ...]:
    _validate_skill_groups(value=skill_groups)
    _validate_patterns(value=patterns)
    _validate_skill_definitions(value=skill_definitions)

    skill_definitions_by_id = {
        definition.skill_id: definition for definition in skill_definitions
    }
    _validate_group_skill_references(
        skill_groups=skill_groups,
        skill_definitions_by_id=skill_definitions_by_id,
    )

    skill_groups_by_id = {group.group_id: group for group in skill_groups}
    _validate_pattern_group_references(
        patterns=patterns,
        skill_groups_by_id=skill_groups_by_id,
    )

    generated: list[EquipmentDefinition] = []
    seen_signatures: set[
        tuple[tuple[tuple[str, int], ...], tuple[DecorationSlot, ...]]
    ] = set()

    for pattern in patterns:
        option_groups = tuple(
            skill_groups_by_id[group_id].skills for group_id in pattern.skill_group_ids
        )
        for combination_index, selected_skills in enumerate(
            product(*option_groups),
            start=1,
        ):
            aggregated_skills = _aggregate_selected_skills(
                selected_skills=selected_skills,
                skill_definitions_by_id=skill_definitions_by_id,
            )
            signature = (
                tuple(
                    sorted((skill.skill_id, skill.level) for skill in aggregated_skills)
                ),
                pattern.slots,
            )
            if signature in seen_signatures:
                continue

            seen_signatures.add(signature)
            generated.append(
                EquipmentDefinition(
                    equipment_id=(
                        "generated:appraisal-charm:"
                        f"rarity-{pattern.rarity}:{pattern.pattern_id}:"
                        f"combination-{combination_index}"
                    ),
                    part=EquipmentPart.CHARM,
                    skills=aggregated_skills,
                    slots=pattern.slots,
                    series_skill_id=None,
                    group_skill_id=None,
                    allows_series_skill_assignment=False,
                    allows_group_skill_assignment=False,
                )
            )

    return tuple(generated)


def _validate_skill_groups(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("skill_groups must be tuple")

    seen_group_ids: set[str] = set()
    for group in value:
        if not isinstance(group, AppraisalCharmSkillGroupDefinition):
            raise TypeError(
                "skill_groups must contain only AppraisalCharmSkillGroupDefinition"
            )

        if group.group_id in seen_group_ids:
            raise ValueError("skill_groups must not contain duplicate group_id")

        seen_group_ids.add(group.group_id)


def _validate_patterns(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("patterns must be tuple")

    seen_pattern_ids: set[str] = set()
    for pattern in value:
        if not isinstance(pattern, AppraisalCharmPatternDefinition):
            raise TypeError(
                "patterns must contain only AppraisalCharmPatternDefinition"
            )

        if pattern.pattern_id in seen_pattern_ids:
            raise ValueError("patterns must not contain duplicate pattern_id")

        seen_pattern_ids.add(pattern.pattern_id)


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


def _validate_group_skill_references(
    *,
    skill_groups: tuple[AppraisalCharmSkillGroupDefinition, ...],
    skill_definitions_by_id: dict[str, SkillDefinition],
) -> None:
    for group in skill_groups:
        for contribution in group.skills:
            definition = skill_definitions_by_id.get(contribution.skill_id)
            if definition is None:
                raise ValueError(
                    "skill_groups skills must reference an existing "
                    "skill_definitions skill"
                )

            if definition.kind not in (SkillKind.ARMOR, SkillKind.WEAPON):
                raise ValueError(
                    "skill_groups skills must reference an armor or weapon "
                    "skill_definitions skill"
                )

            if contribution.level > definition.ranks[-1].level:
                raise ValueError(
                    "skill_groups skill level must not exceed the "
                    "skill_definitions maximum rank"
                )


def _validate_pattern_group_references(
    *,
    patterns: tuple[AppraisalCharmPatternDefinition, ...],
    skill_groups_by_id: dict[str, AppraisalCharmSkillGroupDefinition],
) -> None:
    for pattern in patterns:
        for group_id in pattern.skill_group_ids:
            if group_id not in skill_groups_by_id:
                raise ValueError(
                    "patterns skill_group_ids must reference an existing skill_groups "
                    "group"
                )


def _aggregate_selected_skills(
    *,
    selected_skills: tuple[SkillContribution, ...],
    skill_definitions_by_id: dict[str, SkillDefinition],
) -> tuple[SkillContribution, ...]:
    totals: dict[str, int] = {}
    for contribution in selected_skills:
        totals.setdefault(contribution.skill_id, 0)
        totals[contribution.skill_id] += contribution.level

        maximum_level = skill_definitions_by_id[contribution.skill_id].ranks[-1].level
        if totals[contribution.skill_id] > maximum_level:
            raise ValueError(
                "skill_groups selected skill total must not exceed the "
                "skill_definitions maximum rank"
            )

    return tuple(
        SkillContribution(skill_id=skill_id, level=level)
        for skill_id, level in totals.items()
    )
