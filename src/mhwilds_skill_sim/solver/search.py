"""Build candidate search."""

from __future__ import annotations

from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, WeaponKind
from mhwilds_skill_sim.domain.skill import SkillDefinition
from mhwilds_skill_sim.solver.build import BuildCandidate, enumerate_build_candidates
from mhwilds_skill_sim.solver.equipment_filtering import (
    filter_equipment_candidates_by_weapon_kind,
)
from mhwilds_skill_sim.solver.filtering import (
    filter_build_candidates_by_skill_requirements,
)
from mhwilds_skill_sim.solver.requirements import SkillRequirement


def search_build_candidates_by_skill_requirements(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
    requirements: tuple[SkillRequirement, ...],
    weapon_kind: WeaponKind | None = None,
    skill_definitions: tuple[SkillDefinition, ...] = (),
    appraisal_charm_skill_groups: tuple[AppraisalCharmSkillGroupDefinition, ...] = (),
    appraisal_charm_patterns: tuple[AppraisalCharmPatternDefinition, ...] = (),
) -> tuple[BuildCandidate, ...]:
    filtered_equipment = filter_equipment_candidates_by_weapon_kind(
        equipment=equipment,
        weapon_kind=weapon_kind,
    )
    candidates = enumerate_build_candidates(
        equipment=filtered_equipment,
        decorations=decorations,
        skill_definitions=skill_definitions,
        appraisal_charm_skill_groups=appraisal_charm_skill_groups,
        appraisal_charm_patterns=appraisal_charm_patterns,
    )
    return filter_build_candidates_by_skill_requirements(
        candidates=candidates,
        requirements=requirements,
    )
