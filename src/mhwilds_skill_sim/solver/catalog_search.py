"""Catalog-backed build candidate search."""

from __future__ import annotations

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.requirements import SkillRequirement
from mhwilds_skill_sim.solver.search import (
    search_build_candidates_by_skill_requirements,
)


def search_catalog_build_candidates_by_skill_requirements(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
) -> tuple[BuildCandidate, ...]:
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")

    return search_build_candidates_by_skill_requirements(
        equipment=catalog.equipment,
        decorations=catalog.decorations,
        requirements=requirements,
        skill_definitions=catalog.skills,
        appraisal_charm_skill_groups=catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=catalog.appraisal_charm_patterns,
    )
