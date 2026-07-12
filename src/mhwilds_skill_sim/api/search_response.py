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
                "display_name": equipment.display_name,
                "part": equipment.part.value,
                "weapon_kind": (
                    equipment.weapon_kind.value
                    if equipment.weapon_kind is not None
                    else None
                ),
                "series_skill_id": equipment.series_skill_id,
                "group_skill_id": equipment.group_skill_id,
                "skills": [
                    {
                        "skill_id": skill.skill_id,
                        "level": skill.level,
                    }
                    for skill in equipment.skills
                ],
                "slots": [
                    {
                        "kind": slot.kind.value,
                        "level": slot.level,
                    }
                    for slot in equipment.slots
                ],
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
