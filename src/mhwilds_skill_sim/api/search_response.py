"""API response serializers for search results."""

from __future__ import annotations

from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.search_result import BuildCandidateSearchResult


def build_candidate_to_response(
    *,
    candidate: BuildCandidate,
) -> dict[str, object]:
    if not isinstance(candidate, BuildCandidate):
        raise TypeError("candidate must be BuildCandidate")

    return {
        "equipment": [
            {
                "equipment_id": equipment.equipment_id,
                "part": equipment.part.value,
                "series_skill_id": equipment.series_skill_id,
                "group_skill_id": equipment.group_skill_id,
            }
            for equipment in candidate.equipment
        ],
        "placements": [
            {
                "equipment_id": placement.equipment_id,
                "slot_index": placement.slot_index,
                "decoration_id": placement.decoration_id,
            }
            for placement in candidate.placements
        ],
        "skill_levels": [
            {
                "skill_id": skill_id,
                "level": level,
            }
            for skill_id, level in candidate.skill_levels
        ],
    }


def build_candidate_search_result_to_response(
    *,
    result: BuildCandidateSearchResult,
) -> dict[str, object]:
    if not isinstance(result, BuildCandidateSearchResult):
        raise TypeError("result must be BuildCandidateSearchResult")

    return {
        "candidates": [
            build_candidate_to_response(candidate=candidate)
            for candidate in result.candidates
        ],
        "total_count": result.total_count,
        "truncated": result.truncated,
    }
