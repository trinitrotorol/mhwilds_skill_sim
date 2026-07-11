"""Catalog model containers."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.domain.skill import SkillDefinition, SkillKind


@dataclass(frozen=True, slots=True)
class Catalog:
    schema_version: int
    equipment: tuple[EquipmentDefinition, ...]
    decorations: tuple[DecorationDefinition, ...]
    skills: tuple[SkillDefinition, ...] = ()
    appraisal_charm_skill_groups: tuple[AppraisalCharmSkillGroupDefinition, ...] = ()
    appraisal_charm_patterns: tuple[AppraisalCharmPatternDefinition, ...] = ()

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int:
            raise TypeError("schema_version must be int")

        if self.schema_version < 1:
            raise ValueError("schema_version must be at least 1")

        if type(self.equipment) is not tuple:
            raise TypeError("equipment must be tuple")

        seen_equipment_ids: set[str] = set()
        for equipment in self.equipment:
            if not isinstance(equipment, EquipmentDefinition):
                raise TypeError("equipment must contain only EquipmentDefinition")

            if equipment.equipment_id in seen_equipment_ids:
                raise ValueError("equipment must not contain duplicate equipment_id")

            seen_equipment_ids.add(equipment.equipment_id)

        if type(self.decorations) is not tuple:
            raise TypeError("decorations must be tuple")

        seen_decoration_ids: set[str] = set()
        for decoration in self.decorations:
            if not isinstance(decoration, DecorationDefinition):
                raise TypeError("decorations must contain only DecorationDefinition")

            if decoration.decoration_id in seen_decoration_ids:
                raise ValueError("decorations must not contain duplicate decoration_id")

            seen_decoration_ids.add(decoration.decoration_id)

        if type(self.skills) is not tuple:
            raise TypeError("skills must be tuple")

        seen_skill_ids: set[str] = set()
        for skill in self.skills:
            if not isinstance(skill, SkillDefinition):
                raise TypeError("skills must contain only SkillDefinition")

            if skill.skill_id in seen_skill_ids:
                raise ValueError("skills must not contain duplicate skill_id")

            seen_skill_ids.add(skill.skill_id)

        if type(self.appraisal_charm_skill_groups) is not tuple:
            raise TypeError("appraisal_charm_skill_groups must be tuple")

        seen_appraisal_group_ids: set[str] = set()
        for group in self.appraisal_charm_skill_groups:
            if not isinstance(group, AppraisalCharmSkillGroupDefinition):
                raise TypeError(
                    "appraisal_charm_skill_groups must contain only "
                    "AppraisalCharmSkillGroupDefinition"
                )

            if group.group_id in seen_appraisal_group_ids:
                raise ValueError(
                    "appraisal_charm_skill_groups must not contain duplicate group_id"
                )

            seen_appraisal_group_ids.add(group.group_id)

        if type(self.appraisal_charm_patterns) is not tuple:
            raise TypeError("appraisal_charm_patterns must be tuple")

        seen_appraisal_pattern_ids: set[str] = set()
        for pattern in self.appraisal_charm_patterns:
            if not isinstance(pattern, AppraisalCharmPatternDefinition):
                raise TypeError(
                    "appraisal_charm_patterns must contain only "
                    "AppraisalCharmPatternDefinition"
                )

            if pattern.pattern_id in seen_appraisal_pattern_ids:
                raise ValueError(
                    "appraisal_charm_patterns must not contain duplicate pattern_id"
                )

            seen_appraisal_pattern_ids.add(pattern.pattern_id)

        skills_by_id = {skill.skill_id: skill for skill in self.skills}
        has_series_skill = any(skill.kind is SkillKind.SERIES for skill in self.skills)
        has_group_skill = any(skill.kind is SkillKind.GROUP for skill in self.skills)
        for equipment in self.equipment:
            if equipment.series_skill_id is not None:
                series_skill = skills_by_id.get(equipment.series_skill_id)
                if series_skill is None:
                    raise ValueError(
                        "equipment series_skill_id must reference an existing skill"
                    )
                if series_skill.kind is not SkillKind.SERIES:
                    raise ValueError(
                        "equipment series_skill_id must reference a series skill"
                    )

            if equipment.group_skill_id is not None:
                group_skill = skills_by_id.get(equipment.group_skill_id)
                if group_skill is None:
                    raise ValueError(
                        "equipment group_skill_id must reference an existing skill"
                    )
                if group_skill.kind is not SkillKind.GROUP:
                    raise ValueError(
                        "equipment group_skill_id must reference a group skill"
                    )

            if equipment.allows_series_skill_assignment and not has_series_skill:
                raise ValueError(
                    "equipment allows_series_skill_assignment requires a series skill"
                )

            if equipment.allows_group_skill_assignment and not has_group_skill:
                raise ValueError(
                    "equipment allows_group_skill_assignment requires a group skill"
                )

        for group in self.appraisal_charm_skill_groups:
            for contribution in group.skills:
                referenced_skill = skills_by_id.get(contribution.skill_id)
                if referenced_skill is None:
                    raise ValueError(
                        "appraisal_charm_skill_groups skills must reference an "
                        "existing skill"
                    )

                if referenced_skill.kind not in (SkillKind.ARMOR, SkillKind.WEAPON):
                    raise ValueError(
                        "appraisal_charm_skill_groups skills must reference an "
                        "armor or weapon skill"
                    )

                if contribution.level > referenced_skill.ranks[-1].level:
                    raise ValueError(
                        "appraisal_charm_skill_groups skill level must not exceed "
                        "the referenced skill maximum rank"
                    )

        appraisal_groups_by_id = {
            group.group_id: group for group in self.appraisal_charm_skill_groups
        }
        for pattern in self.appraisal_charm_patterns:
            for group_id in pattern.skill_group_ids:
                if group_id not in appraisal_groups_by_id:
                    raise ValueError(
                        "appraisal_charm_patterns skill_group_ids must reference "
                        "an existing appraisal charm skill group"
                    )
