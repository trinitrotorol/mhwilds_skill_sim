"""API response serializer for ranked CP-SAT search results."""

from __future__ import annotations

from mhwilds_skill_sim.api.search_response import build_candidate_to_response
from mhwilds_skill_sim.solver.cp_sat_search import CpSatBuildSearchResult
from mhwilds_skill_sim.solver.preferences import (
    SkillPreference,
    calculate_skill_preference_score,
)


def build_ranked_cp_sat_search_result_to_response(
    *,
    result: CpSatBuildSearchResult,
    preferences: tuple[SkillPreference, ...],
) -> dict[str, object]:
    if not isinstance(result, CpSatBuildSearchResult):
        raise TypeError("result must be CpSatBuildSearchResult")

    # Validate preferences even when the result contains no candidates.
    calculate_skill_preference_score(
        skill_levels={},
        preferences=preferences,
    )

    candidates: list[dict[str, object]] = []
    for candidate in result.candidates:
        candidate_response = build_candidate_to_response(candidate=candidate)
        candidate_response["preference_score"] = calculate_skill_preference_score(
            skill_levels=dict(candidate.skill_levels),
            preferences=preferences,
        )
        candidates.append(candidate_response)

    return {
        "candidates": candidates,
        "exhausted": result.exhausted,
        "timed_out": result.timed_out,
    }
