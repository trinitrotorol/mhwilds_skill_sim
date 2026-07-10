"""Build candidate search."""

from __future__ import annotations

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition
from mhwilds_skill_sim.domain.skill import SkillDefinition
from mhwilds_skill_sim.solver.build import BuildCandidate, enumerate_build_candidates
from mhwilds_skill_sim.solver.filtering import (
    filter_build_candidates_by_skill_requirements,
)
from mhwilds_skill_sim.solver.requirements import SkillRequirement


def search_build_candidates_by_skill_requirements(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
    requirements: tuple[SkillRequirement, ...],
    skill_definitions: tuple[SkillDefinition, ...] = (),
) -> tuple[BuildCandidate, ...]:
    candidates = enumerate_build_candidates(
        equipment=equipment,
        decorations=decorations,
        skill_definitions=skill_definitions,
    )
    return filter_build_candidates_by_skill_requirements(
        candidates=candidates,
        requirements=requirements,
    )
