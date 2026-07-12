"""Solver helpers."""

from mhwilds_skill_sim.solver.appraisal_charms import (
    generate_appraisal_charm_equipment_candidates,
)
from mhwilds_skill_sim.solver.build import (
    BuildCandidate,
    enumerate_build_candidates,
)
from mhwilds_skill_sim.solver.catalog_search import (
    search_catalog_build_candidates_by_skill_requirements,
)
from mhwilds_skill_sim.solver.decoration import (
    enumerate_decoration_placement_combinations,
)
from mhwilds_skill_sim.solver.equipment import enumerate_equipment_selections
from mhwilds_skill_sim.solver.equipment_variants import (
    expand_equipment_bonus_skill_variants,
)
from mhwilds_skill_sim.solver.equipment_filtering import (
    filter_equipment_candidates_by_weapon_kind,
)
from mhwilds_skill_sim.solver.filtering import (
    filter_build_candidates_by_skill_requirements,
)
from mhwilds_skill_sim.solver.requirements import (
    SkillRequirement,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.solver.search import (
    search_build_candidates_by_skill_requirements,
)
from mhwilds_skill_sim.solver.search_result import (
    BuildCandidateSearchResult,
    search_limited_catalog_build_candidates_by_skill_requirements,
)

__all__ = [
    "BuildCandidate",
    "BuildCandidateSearchResult",
    "SkillRequirement",
    "enumerate_build_candidates",
    "enumerate_decoration_placement_combinations",
    "enumerate_equipment_selections",
    "expand_equipment_bonus_skill_variants",
    "filter_equipment_candidates_by_weapon_kind",
    "filter_build_candidates_by_skill_requirements",
    "generate_appraisal_charm_equipment_candidates",
    "search_catalog_build_candidates_by_skill_requirements",
    "search_build_candidates_by_skill_requirements",
    "search_limited_catalog_build_candidates_by_skill_requirements",
    "skill_levels_satisfy_requirements",
]
