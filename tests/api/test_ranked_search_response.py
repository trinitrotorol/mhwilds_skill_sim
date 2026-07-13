from __future__ import annotations

import copy
import importlib
import inspect
import json
from dataclasses import is_dataclass
from enum import Enum

import pytest

import mhwilds_skill_sim.api as api
import mhwilds_skill_sim.api.ranked_search_response as ranked_search_response
from mhwilds_skill_sim.api.ranked_search_response import (
    build_ranked_cp_sat_search_result_to_response,
)
from mhwilds_skill_sim.api.search_response import build_candidate_to_response
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.cp_sat_search import CpSatBuildSearchResult
from mhwilds_skill_sim.solver.preferences import SkillPreference
from mhwilds_skill_sim.validation.placement import DecorationPlacement


EXPECTED_API_ALL = [
    "SearchRequest",
    "app",
    "build_candidate_search_result_to_response",
    "build_candidate_to_response",
    "create_app",
    "decode_search_request_payload",
    "search_catalog_build_candidates_from_payload",
]


class PreferenceTuple(tuple[SkillPreference, ...]):
    pass


class CpSatBuildSearchResultSubclass(CpSatBuildSearchResult):
    pass


def equipment_definition(
    part: EquipmentPart = EquipmentPart.WEAPON,
    equipment_id: str = "equipment:weapon:test",
    *,
    skills: tuple[SkillContribution, ...] = (),
    slots: tuple[DecorationSlot, ...] = (),
    display_name: str | None = None,
    weapon_kind: WeaponKind | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=skills,
        slots=slots,
        display_name=display_name,
        weapon_kind=weapon_kind,
    )


def candidate(
    equipment_id: str = "equipment:weapon:test",
    *,
    skill_levels: tuple[tuple[str, int], ...] = (),
) -> BuildCandidate:
    return BuildCandidate(
        equipment=(equipment_definition(equipment_id=equipment_id),),
        placements=(),
        skill_levels=skill_levels,
    )


def detailed_candidate() -> BuildCandidate:
    equipment_id = "equipment:weapon:test"
    return BuildCandidate(
        equipment=(
            equipment_definition(
                equipment_id=equipment_id,
                skills=(SkillContribution(skill_id="skill:attack", level=2),),
                slots=(DecorationSlot(kind=DecorationKind.WEAPON, level=3),),
                display_name="Test Great Sword",
                weapon_kind=WeaponKind.GREAT_SWORD,
            ),
        ),
        placements=(
            DecorationPlacement(
                equipment_id=equipment_id,
                slot_index=0,
                decoration_id="decoration:attack",
            ),
        ),
        skill_levels=(("skill:attack", 3),),
    )


def preference(
    skill_id: str = "skill:attack",
    target_level: int = 1,
) -> SkillPreference:
    return SkillPreference(skill_id=skill_id, target_level=target_level)


def response_contains_unserializable_value(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            response_contains_unserializable_value(key)
            or response_contains_unserializable_value(item)
            for key, item in value.items()
        )

    if isinstance(value, list):
        return any(response_contains_unserializable_value(item) for item in value)

    return isinstance(value, tuple | Enum) or is_dataclass(value)


def test_ranked_response_converts_empty_result_with_exact_top_level_shape() -> None:
    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(),
            exhausted=True,
            timed_out=False,
        ),
        preferences=(),
    )

    assert response == {
        "candidates": [],
        "exhausted": True,
        "timed_out": False,
    }
    assert list(response) == ["candidates", "exhausted", "timed_out"]
    assert "total_count" not in response
    assert "truncated" not in response


def test_ranked_response_appends_score_to_existing_candidate_shape() -> None:
    build = detailed_candidate()

    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(build,),
            exhausted=False,
            timed_out=False,
        ),
        preferences=(preference(target_level=5),),
    )
    serialized = response["candidates"][0]  # type: ignore[index]

    expected = build_candidate_to_response(candidate=build)
    expected["preference_score"] = 3
    assert serialized == expected
    assert list(serialized) == [
        "equipment",
        "placements",
        "skill_levels",
        "preference_score",
    ]
    assert list(serialized["equipment"][0]) == [  # type: ignore[index]
        "equipment_id",
        "display_name",
        "part",
        "weapon_kind",
        "series_skill_id",
        "group_skill_id",
        "series_skill_ids",
        "group_skill_ids",
        "skills",
        "slots",
    ]
    assert list(serialized["placements"][0]) == [  # type: ignore[index]
        "equipment_id",
        "slot_index",
        "decoration_id",
    ]
    assert list(serialized["skill_levels"][0]) == [  # type: ignore[index]
        "skill_id",
        "level",
    ]


def test_ranked_response_preserves_candidate_order_without_sorting_by_score() -> None:
    first = candidate(
        "equipment:weapon:first",
        skill_levels=(("skill:attack", 1),),
    )
    second = candidate(
        "equipment:weapon:second",
        skill_levels=(("skill:attack", 5),),
    )

    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(first, second),
            exhausted=False,
            timed_out=False,
        ),
        preferences=(preference(target_level=5),),
    )
    candidates = response["candidates"]

    assert [item["equipment"][0]["equipment_id"] for item in candidates] == [  # type: ignore[index]
        "equipment:weapon:first",
        "equipment:weapon:second",
    ]
    assert [item["preference_score"] for item in candidates] == [1, 5]  # type: ignore[index]


def test_ranked_response_score_caps_targets_and_sums_multiple_preferences() -> None:
    build = candidate(
        skill_levels=(
            ("skill:attack", 7),
            ("skill:critical-eye", 2),
        ),
    )

    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(build,),
            exhausted=True,
            timed_out=False,
        ),
        preferences=(
            preference("skill:attack", 3),
            preference("skill:critical-eye", 5),
        ),
    )
    score = response["candidates"][0]["preference_score"]  # type: ignore[index]

    assert score == 5
    assert type(score) is int


@pytest.mark.parametrize(
    "preferences",
    [
        (),
        (preference("skill:unknown", 5),),
    ],
)
def test_ranked_response_scores_empty_or_unknown_preferences_as_zero(
    preferences: tuple[SkillPreference, ...],
) -> None:
    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(candidate(skill_levels=(("skill:attack", 3),)),),
            exhausted=False,
            timed_out=False,
        ),
        preferences=preferences,
    )

    assert response["candidates"][0]["preference_score"] == 0  # type: ignore[index]


@pytest.mark.parametrize(
    ("exhausted", "timed_out"),
    [
        (True, False),
        (False, False),
        (False, True),
    ],
)
def test_ranked_response_preserves_search_state(
    exhausted: bool,
    timed_out: bool,
) -> None:
    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(candidate(),) if timed_out else (),
            exhausted=exhausted,
            timed_out=timed_out,
        ),
        preferences=(),
    )

    assert response["exhausted"] is exhausted
    assert response["timed_out"] is timed_out


def test_ranked_response_is_json_serializable() -> None:
    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(detailed_candidate(),),
            exhausted=False,
            timed_out=True,
        ),
        preferences=(preference(target_level=3),),
    )

    json.dumps(response)
    assert not response_contains_unserializable_value(response)


def test_ranked_response_reuses_candidate_serializer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = candidate("equipment:weapon:first")
    second = candidate("equipment:weapon:second")
    calls: list[BuildCandidate] = []

    def fake_candidate_serializer(*, candidate: BuildCandidate) -> dict[str, object]:
        calls.append(candidate)
        return {"equipment_id": candidate.equipment[0].equipment_id}

    monkeypatch.setattr(
        ranked_search_response,
        "build_candidate_to_response",
        fake_candidate_serializer,
    )

    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(first, second),
            exhausted=False,
            timed_out=False,
        ),
        preferences=(),
    )

    assert calls == [first, second]
    assert response["candidates"] == [
        {"equipment_id": "equipment:weapon:first", "preference_score": 0},
        {"equipment_id": "equipment:weapon:second", "preference_score": 0},
    ]


def test_ranked_response_recalculates_score_from_public_skill_levels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = candidate(
        skill_levels=(
            ("skill:attack", 4),
            ("skill:critical-eye", 2),
        ),
    )
    preferences = (preference("skill:attack", 3),)
    calls: list[tuple[dict[str, int], tuple[SkillPreference, ...]]] = []

    def fake_score(
        *,
        skill_levels: dict[str, int],
        preferences: tuple[SkillPreference, ...],
    ) -> int:
        calls.append((skill_levels, preferences))
        return 37

    monkeypatch.setattr(
        ranked_search_response,
        "calculate_skill_preference_score",
        fake_score,
    )

    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(build,),
            exhausted=True,
            timed_out=False,
        ),
        preferences=preferences,
    )

    assert calls == [
        ({}, preferences),
        ({"skill:attack": 4, "skill:critical-eye": 2}, preferences),
    ]
    assert calls[1][0] is not calls[0][0]
    assert response["candidates"][0]["preference_score"] == 37  # type: ignore[index]


def test_ranked_response_accepts_result_subclass() -> None:
    response = build_ranked_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResultSubclass(
            candidates=(),
            exhausted=True,
            timed_out=False,
        ),
        preferences=(),
    )

    assert response["candidates"] == []


@pytest.mark.parametrize("invalid_result", ["result", {}, None])
def test_ranked_response_rejects_invalid_result(invalid_result: object) -> None:
    with pytest.raises(TypeError, match="result"):
        build_ranked_cp_sat_search_result_to_response(
            result=invalid_result,  # type: ignore[arg-type]
            preferences=(),
        )


@pytest.mark.parametrize(
    "invalid_preferences",
    [
        [],
        {preference()},
        PreferenceTuple((preference(),)),
        None,
    ],
)
def test_ranked_response_requires_exact_preference_tuple(
    invalid_preferences: object,
) -> None:
    with pytest.raises(TypeError, match="preferences"):
        build_ranked_cp_sat_search_result_to_response(
            result=CpSatBuildSearchResult(
                candidates=(),
                exhausted=True,
                timed_out=False,
            ),
            preferences=invalid_preferences,  # type: ignore[arg-type]
        )


def test_ranked_response_rejects_invalid_preference_item_with_no_candidates() -> None:
    with pytest.raises(TypeError, match="preferences"):
        build_ranked_cp_sat_search_result_to_response(
            result=CpSatBuildSearchResult(
                candidates=(),
                exhausted=True,
                timed_out=False,
            ),
            preferences=("skill:attack",),  # type: ignore[arg-type]
        )


def test_ranked_response_rejects_duplicate_preferences_with_no_candidates() -> None:
    with pytest.raises(ValueError, match="preferences"):
        build_ranked_cp_sat_search_result_to_response(
            result=CpSatBuildSearchResult(
                candidates=(),
                exhausted=True,
                timed_out=False,
            ),
            preferences=(
                preference("skill:attack", 1),
                preference("skill:attack", 2),
            ),
        )


def test_ranked_response_requires_exact_keyword_only_signature() -> None:
    signature = inspect.signature(build_ranked_cp_sat_search_result_to_response)

    assert list(signature.parameters) == ["result", "preferences"]
    assert signature.parameters["result"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["preferences"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        build_ranked_cp_sat_search_result_to_response(
            CpSatBuildSearchResult(
                candidates=(),
                exhausted=True,
                timed_out=False,
            ),
            (),
        )  # type: ignore[misc]


def test_ranked_response_returns_fully_independent_containers() -> None:
    result = CpSatBuildSearchResult(
        candidates=(detailed_candidate(),),
        exhausted=False,
        timed_out=True,
    )
    preferences = (preference(target_level=3),)

    first = build_ranked_cp_sat_search_result_to_response(
        result=result,
        preferences=preferences,
    )
    second = build_ranked_cp_sat_search_result_to_response(
        result=result,
        preferences=preferences,
    )
    first_candidates = first["candidates"]
    second_candidates = second["candidates"]
    first_candidate = first_candidates[0]  # type: ignore[index]
    second_candidate = second_candidates[0]  # type: ignore[index]
    first_equipment = first_candidate["equipment"]
    second_equipment = second_candidate["equipment"]
    first_item = first_equipment[0]
    second_item = second_equipment[0]

    assert first is not second
    assert first_candidates is not second_candidates
    assert first_candidate is not second_candidate
    assert first_equipment is not second_equipment
    assert first_item is not second_item
    assert first_item["series_skill_ids"] is not second_item["series_skill_ids"]
    assert first_item["group_skill_ids"] is not second_item["group_skill_ids"]
    assert first_item["skills"] is not second_item["skills"]
    assert first_item["skills"][0] is not second_item["skills"][0]
    assert first_item["slots"] is not second_item["slots"]
    assert first_item["slots"][0] is not second_item["slots"][0]
    assert first_candidate["placements"] is not second_candidate["placements"]
    assert first_candidate["placements"][0] is not second_candidate["placements"][0]
    assert first_candidate["skill_levels"] is not second_candidate["skill_levels"]
    assert first_candidate["skill_levels"][0] is not second_candidate["skill_levels"][0]

    first_item["skills"].append({"skill_id": "changed", "level": 99})
    assert second == build_ranked_cp_sat_search_result_to_response(
        result=result,
        preferences=preferences,
    )


def test_ranked_response_does_not_mutate_inputs() -> None:
    build = detailed_candidate()
    result = CpSatBuildSearchResult(
        candidates=(build,),
        exhausted=False,
        timed_out=True,
    )
    preferences = (preference(target_level=3),)
    result_before = copy.deepcopy(result)
    preferences_before = copy.deepcopy(preferences)

    build_ranked_cp_sat_search_result_to_response(
        result=result,
        preferences=preferences,
    )

    assert result == result_before
    assert result.candidates[0] is build
    assert build == result_before.candidates[0]
    assert preferences == preferences_before


def test_ranked_response_direct_module_import() -> None:
    imported_module = importlib.import_module(
        "mhwilds_skill_sim.api.ranked_search_response",
    )

    assert (
        imported_module.build_ranked_cp_sat_search_result_to_response
        is build_ranked_cp_sat_search_result_to_response
    )


def test_ranked_response_is_not_package_exported() -> None:
    assert "build_ranked_cp_sat_search_result_to_response" not in api.__all__
    assert not hasattr(api, "build_ranked_cp_sat_search_result_to_response")
    assert api.__all__ == EXPECTED_API_ALL
