"""Build candidate filtering."""

from __future__ import annotations

from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.requirements import (
    SkillRequirement,
    skill_levels_satisfy_requirements,
)


def filter_build_candidates_by_skill_requirements(
    *,
    candidates: tuple[BuildCandidate, ...],
    requirements: tuple[SkillRequirement, ...],
) -> tuple[BuildCandidate, ...]:
    if type(candidates) is not tuple:
        raise TypeError("candidates must be tuple")

    if type(requirements) is not tuple:
        raise TypeError("requirements must be tuple")

    for candidate in candidates:
        if not isinstance(candidate, BuildCandidate):
            raise TypeError("candidates must contain only BuildCandidate")

    _validate_requirements(requirements=requirements)

    return tuple(
        candidate
        for candidate in candidates
        if skill_levels_satisfy_requirements(
            skill_levels=dict(candidate.skill_levels),
            requirements=requirements,
        )
    )


def _validate_requirements(*, requirements: tuple[SkillRequirement, ...]) -> None:
    seen_skill_ids: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, SkillRequirement):
            raise TypeError("requirements must contain only SkillRequirement")

        if requirement.skill_id in seen_skill_ids:
            raise ValueError("requirements must not contain duplicate skill_id")

        seen_skill_ids.add(requirement.skill_id)
