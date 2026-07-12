"""Search result containers."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import WeaponKind
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.catalog_search import (
    search_catalog_build_candidates_by_skill_requirements,
)
from mhwilds_skill_sim.solver.requirements import SkillRequirement


@dataclass(frozen=True, slots=True)
class BuildCandidateSearchResult:
    candidates: tuple[BuildCandidate, ...]
    total_count: int
    truncated: bool

    def __post_init__(self) -> None:
        _validate_candidates(value=self.candidates)
        _validate_total_count(value=self.total_count)
        _validate_truncated(value=self.truncated)
        _validate_result_consistency(
            candidates=self.candidates,
            total_count=self.total_count,
            truncated=self.truncated,
        )


def search_limited_catalog_build_candidates_by_skill_requirements(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    max_results: int,
    weapon_kind: WeaponKind | None = None,
) -> BuildCandidateSearchResult:
    _validate_max_results(value=max_results)

    all_candidates = search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=requirements,
        weapon_kind=weapon_kind,
    )
    limited_candidates = all_candidates[:max_results]
    return BuildCandidateSearchResult(
        candidates=limited_candidates,
        total_count=len(all_candidates),
        truncated=len(limited_candidates) < len(all_candidates),
    )


def _validate_candidates(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("candidates must be tuple")

    for candidate in value:
        if not isinstance(candidate, BuildCandidate):
            raise TypeError("candidates must contain only BuildCandidate")


def _validate_total_count(*, value: object) -> None:
    if type(value) is not int:
        raise TypeError("total_count must be int")

    if value < 0:
        raise ValueError("total_count must be at least 0")


def _validate_truncated(*, value: object) -> None:
    if type(value) is not bool:
        raise TypeError("truncated must be bool")


def _validate_result_consistency(
    *,
    candidates: tuple[BuildCandidate, ...],
    total_count: int,
    truncated: bool,
) -> None:
    candidate_count = len(candidates)

    if candidate_count > total_count:
        raise ValueError("candidates length must not exceed total_count")

    if not truncated and candidate_count != total_count:
        raise ValueError(
            "truncated False requires candidates length to equal total_count",
        )

    if truncated and candidate_count >= total_count:
        raise ValueError(
            "truncated True requires candidates length to be less than total_count",
        )


def _validate_max_results(*, value: object) -> None:
    if type(value) is not int:
        raise TypeError("max_results must be int")

    if value < 0:
        raise ValueError("max_results must be at least 0")
