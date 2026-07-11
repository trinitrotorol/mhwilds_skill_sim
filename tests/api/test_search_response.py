from __future__ import annotations

import inspect
import json
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path

import pytest

from mhwilds_skill_sim.api.search_response import (
    build_candidate_search_result_to_response,
    build_candidate_to_response,
)
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.search_result import BuildCandidateSearchResult
from mhwilds_skill_sim.validation.placement import DecorationPlacement


def equipment_definition(
    part: EquipmentPart = EquipmentPart.WEAPON,
    equipment_id: str | None = None,
    *,
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
    skills: tuple[SkillContribution, ...] = (),
    slots: tuple[DecorationSlot, ...] = (),
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=slots,
        series_skill_id=series_skill_id,
        group_skill_id=group_skill_id,
    )


def placement(
    equipment_id: str = "equipment:weapon",
    slot_index: int = 0,
    decoration_id: str = "decoration:attack",
) -> DecorationPlacement:
    return DecorationPlacement(
        equipment_id=equipment_id,
        slot_index=slot_index,
        decoration_id=decoration_id,
    )


def candidate(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    placements: tuple[DecorationPlacement, ...] = (),
    skill_levels: tuple[tuple[str, int], ...] = (("skill:attack-boost", 1),),
) -> BuildCandidate:
    return BuildCandidate(
        equipment=equipment if equipment is not None else (equipment_definition(),),
        placements=placements,
        skill_levels=skill_levels,
    )


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


def test_build_candidate_to_response_converts_candidate_to_dict() -> None:
    build = candidate(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, "equipment:weapon"),
            equipment_definition(EquipmentPart.HEAD, "equipment:head"),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:attack"),
            placement("equipment:head", 1, "decoration:expert"),
        ),
        skill_levels=(
            ("skill:attack-boost", 3),
            ("skill:critical-eye", 2),
        ),
    )

    response = build_candidate_to_response(candidate=build)

    assert response == {
        "equipment": [
            {
                "equipment_id": "equipment:weapon",
                "part": "weapon",
                "series_skill_id": None,
                "group_skill_id": None,
                "skills": [],
                "slots": [],
            },
            {
                "equipment_id": "equipment:head",
                "part": "head",
                "series_skill_id": None,
                "group_skill_id": None,
                "skills": [],
                "slots": [],
            },
        ],
        "placements": [
            {
                "equipment_id": "equipment:weapon",
                "slot_index": 0,
                "decoration_id": "decoration:attack",
            },
            {
                "equipment_id": "equipment:head",
                "slot_index": 1,
                "decoration_id": "decoration:expert",
            },
        ],
        "skill_levels": [
            {
                "skill_id": "skill:attack-boost",
                "level": 3,
            },
            {
                "skill_id": "skill:critical-eye",
                "level": 2,
            },
        ],
    }


def test_build_candidate_to_response_key_order() -> None:
    response = build_candidate_to_response(
        candidate=candidate(placements=(placement(),))
    )

    assert list(response) == ["equipment", "placements", "skill_levels"]
    assert list(response["equipment"][0]) == [  # type: ignore[index]
        "equipment_id",
        "part",
        "series_skill_id",
        "group_skill_id",
        "skills",
        "slots",
    ]
    assert list(response["placements"][0]) == [  # type: ignore[index]
        "equipment_id",
        "slot_index",
        "decoration_id",
    ]
    assert list(response["skill_levels"][0]) == ["skill_id", "level"]  # type: ignore[index]


def test_build_candidate_to_response_uses_equipment_part_value() -> None:
    response = build_candidate_to_response(
        candidate=candidate(
            equipment=(equipment_definition(EquipmentPart.CHARM, "equipment:charm"),),
        ),
    )

    assert response["equipment"] == [
        {
            "equipment_id": "equipment:charm",
            "part": "charm",
            "series_skill_id": None,
            "group_skill_id": None,
            "skills": [],
            "slots": [],
        },
    ]


def test_build_candidate_to_response_serializes_membership_values() -> None:
    response = build_candidate_to_response(
        candidate=candidate(
            equipment=(
                equipment_definition(
                    equipment_id="equipment:weapon",
                    series_skill_id="skill:series-bonus",
                    group_skill_id="skill:group-bonus",
                ),
                equipment_definition(
                    EquipmentPart.HEAD,
                    "equipment:head",
                ),
            ),
        ),
    )

    assert response["equipment"] == [
        {
            "equipment_id": "equipment:weapon",
            "part": "weapon",
            "series_skill_id": "skill:series-bonus",
            "group_skill_id": "skill:group-bonus",
            "skills": [],
            "slots": [],
        },
        {
            "equipment_id": "equipment:head",
            "part": "head",
            "series_skill_id": None,
            "group_skill_id": None,
            "skills": [],
            "slots": [],
        },
    ]


def test_same_equipment_id_variants_serialize_with_distinct_memberships() -> None:
    response = build_candidate_search_result_to_response(
        result=BuildCandidateSearchResult(
            candidates=(
                candidate(
                    equipment=(
                        equipment_definition(
                            equipment_id="equipment:weapon:artian",
                            series_skill_id="skill:series-a",
                            group_skill_id="skill:group-a",
                        ),
                    ),
                ),
                candidate(
                    equipment=(
                        equipment_definition(
                            equipment_id="equipment:weapon:artian",
                            series_skill_id="skill:series-b",
                            group_skill_id="skill:group-b",
                        ),
                    ),
                ),
            ),
            total_count=2,
            truncated=False,
        ),
    )

    equipment_responses = [
        candidate_response["equipment"][0]  # type: ignore[index]
        for candidate_response in response["candidates"]  # type: ignore[union-attr]
    ]
    assert (
        equipment_responses[0]["equipment_id"] == equipment_responses[1]["equipment_id"]
    )
    assert equipment_responses[0]["series_skill_id"] == "skill:series-a"
    assert equipment_responses[1]["series_skill_id"] == "skill:series-b"
    assert "allows_series_skill_assignment" not in equipment_responses[0]
    assert "allows_group_skill_assignment" not in equipment_responses[0]


def test_build_candidate_to_response_serializes_fixed_equipment_skills_and_slots() -> (
    None
):
    response = build_candidate_to_response(
        candidate=candidate(
            equipment=(
                equipment_definition(
                    EquipmentPart.HEAD,
                    "equipment:head:fixed",
                    skills=(
                        SkillContribution("skill:critical-eye", 2),
                        SkillContribution("skill:weakness-exploit", 1),
                    ),
                    slots=(
                        DecorationSlot(DecorationKind.ARMOR, 3),
                        DecorationSlot(DecorationKind.ARMOR, 1),
                    ),
                ),
            ),
        ),
    )

    assert response["equipment"] == [
        {
            "equipment_id": "equipment:head:fixed",
            "part": "head",
            "series_skill_id": None,
            "group_skill_id": None,
            "skills": [
                {"skill_id": "skill:critical-eye", "level": 2},
                {"skill_id": "skill:weakness-exploit", "level": 1},
            ],
            "slots": [
                {"kind": "armor", "level": 3},
                {"kind": "armor", "level": 1},
            ],
        }
    ]


def test_build_candidate_to_response_serializes_generated_appraisal_charm() -> None:
    response = build_candidate_to_response(
        candidate=candidate(
            equipment=(
                equipment_definition(
                    EquipmentPart.CHARM,
                    ("generated:appraisal-charm:rarity-8:pattern:test:combination-1"),
                    skills=(
                        SkillContribution("skill:attack-boost", 3),
                        SkillContribution("skill:weapon-technique", 1),
                    ),
                    slots=(
                        DecorationSlot(DecorationKind.WEAPON, 1),
                        DecorationSlot(DecorationKind.ARMOR, 1),
                    ),
                ),
            ),
        ),
    )

    charm = response["equipment"][0]  # type: ignore[index]
    assert charm["part"] == "charm"
    assert charm["skills"] == [
        {"skill_id": "skill:attack-boost", "level": 3},
        {"skill_id": "skill:weapon-technique", "level": 1},
    ]
    assert charm["slots"] == [
        {"kind": "weapon", "level": 1},
        {"kind": "armor", "level": 1},
    ]


def test_build_candidate_to_response_preserves_input_order() -> None:
    build = candidate(
        equipment=(
            equipment_definition(EquipmentPart.HEAD, "equipment:head"),
            equipment_definition(EquipmentPart.CHEST, "equipment:chest"),
        ),
        placements=(
            placement("equipment:head", 1, "decoration:expert"),
            placement("equipment:chest", 0, "decoration:attack"),
        ),
        skill_levels=(
            ("skill:critical-eye", 2),
            ("skill:attack-boost", 3),
        ),
    )

    response = build_candidate_to_response(candidate=build)

    assert [item["equipment_id"] for item in response["equipment"]] == [  # type: ignore[index]
        "equipment:head",
        "equipment:chest",
    ]
    assert [item["decoration_id"] for item in response["placements"]] == [  # type: ignore[index]
        "decoration:expert",
        "decoration:attack",
    ]
    assert [item["skill_id"] for item in response["skill_levels"]] == [  # type: ignore[index]
        "skill:critical-eye",
        "skill:attack-boost",
    ]


def test_build_candidate_to_response_empty_values_are_empty_lists() -> None:
    response = build_candidate_to_response(
        candidate=BuildCandidate(equipment=(), placements=(), skill_levels=()),
    )

    assert response == {
        "equipment": [],
        "placements": [],
        "skill_levels": [],
    }


def test_build_candidate_to_response_is_json_serializable() -> None:
    response = build_candidate_to_response(
        candidate=candidate(placements=(placement(),))
    )

    json.dumps(response)
    assert not response_contains_unserializable_value(response)


def test_build_candidate_to_response_returns_new_mutable_containers_each_call() -> None:
    build = candidate(
        equipment=(
            equipment_definition(
                skills=(SkillContribution("skill:attack-boost", 1),),
                slots=(DecorationSlot(DecorationKind.WEAPON, 1),),
            ),
        ),
        placements=(placement(),),
        skill_levels=(("skill:attack-boost", 1),),
    )

    first = build_candidate_to_response(candidate=build)
    second = build_candidate_to_response(candidate=build)

    assert first is not second
    assert first["equipment"] is not second["equipment"]
    assert first["equipment"][0] is not second["equipment"][0]  # type: ignore[index]
    assert first["equipment"][0]["skills"] is not second["equipment"][0]["skills"]  # type: ignore[index]
    assert first["equipment"][0]["slots"] is not second["equipment"][0]["slots"]  # type: ignore[index]
    assert first["equipment"][0]["skills"][0] is not second["equipment"][0]["skills"][0]  # type: ignore[index]
    assert first["equipment"][0]["slots"][0] is not second["equipment"][0]["slots"][0]  # type: ignore[index]
    assert first["placements"] is not second["placements"]
    assert first["skill_levels"] is not second["skill_levels"]

    first["equipment"].append(  # type: ignore[union-attr]
        {
            "equipment_id": "changed",
            "part": "head",
            "series_skill_id": None,
            "group_skill_id": None,
        }
    )
    first["equipment"][0]["skills"][0]["level"] = 999  # type: ignore[index]
    first["equipment"][0]["slots"][0]["level"] = 999  # type: ignore[index]
    first["skill_levels"][0]["level"] = 999  # type: ignore[index]

    assert second == build_candidate_to_response(candidate=build)


def test_build_candidate_to_response_does_not_mutate_candidate() -> None:
    build = candidate(placements=(placement(),))
    before = build

    build_candidate_to_response(candidate=build)

    assert build == before


def test_build_candidate_to_response_requires_keyword_argument() -> None:
    signature = inspect.signature(build_candidate_to_response)

    assert signature.parameters["candidate"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        build_candidate_to_response(candidate())  # type: ignore[call-arg]


@pytest.mark.parametrize("invalid_candidate", ["candidate", {}, None])
def test_build_candidate_to_response_rejects_invalid_candidate(
    invalid_candidate: object,
) -> None:
    with pytest.raises(TypeError, match="candidate"):
        build_candidate_to_response(
            candidate=invalid_candidate,  # type: ignore[arg-type]
        )


def test_build_candidate_to_response_public_import() -> None:
    from mhwilds_skill_sim.api import build_candidate_to_response as exported_function

    assert exported_function is build_candidate_to_response


def test_build_candidate_search_result_to_response_converts_result_to_dict() -> None:
    first = candidate(equipment=(equipment_definition(EquipmentPart.WEAPON),))
    second = candidate(equipment=(equipment_definition(EquipmentPart.HEAD),))
    result = BuildCandidateSearchResult(
        candidates=(first, second),
        total_count=3,
        truncated=True,
    )

    response = build_candidate_search_result_to_response(result=result)

    assert response == {
        "candidates": [
            build_candidate_to_response(candidate=first),
            build_candidate_to_response(candidate=second),
        ],
        "total_count": 3,
        "truncated": True,
    }


def test_build_candidate_search_result_to_response_key_order() -> None:
    response = build_candidate_search_result_to_response(
        result=BuildCandidateSearchResult(
            candidates=(),
            total_count=0,
            truncated=False,
        ),
    )

    assert list(response) == ["candidates", "total_count", "truncated"]


def test_build_candidate_search_result_to_response_preserves_candidate_order() -> None:
    first = candidate(equipment=(equipment_definition(EquipmentPart.WEAPON),))
    second = candidate(equipment=(equipment_definition(EquipmentPart.HEAD),))
    result = BuildCandidateSearchResult(
        candidates=(first, second),
        total_count=2,
        truncated=False,
    )

    response = build_candidate_search_result_to_response(result=result)

    assert response["candidates"] == [
        build_candidate_to_response(candidate=first),
        build_candidate_to_response(candidate=second),
    ]


@pytest.mark.parametrize("truncated", [True, False])
def test_build_candidate_search_result_to_response_preserves_metadata(
    truncated: bool,
) -> None:
    result = BuildCandidateSearchResult(
        candidates=(),
        total_count=1 if truncated else 0,
        truncated=truncated,
    )

    response = build_candidate_search_result_to_response(result=result)

    assert response["total_count"] == result.total_count
    assert response["truncated"] is truncated


def test_build_candidate_search_result_to_response_empty_candidates() -> None:
    response = build_candidate_search_result_to_response(
        result=BuildCandidateSearchResult(
            candidates=(),
            total_count=0,
            truncated=False,
        ),
    )

    assert response["candidates"] == []


def test_build_candidate_search_result_to_response_is_json_serializable() -> None:
    response = build_candidate_search_result_to_response(
        result=BuildCandidateSearchResult(
            candidates=(candidate(placements=(placement(),)),),
            total_count=1,
            truncated=False,
        ),
    )

    json.dumps(response)
    assert not response_contains_unserializable_value(response)


def test_build_candidate_search_result_to_response_returns_new_containers_each_call() -> (
    None
):
    result = BuildCandidateSearchResult(
        candidates=(candidate(placements=(placement(),)),),
        total_count=1,
        truncated=False,
    )

    first = build_candidate_search_result_to_response(result=result)
    second = build_candidate_search_result_to_response(result=result)

    assert first is not second
    assert first["candidates"] is not second["candidates"]
    assert first["candidates"][0] is not second["candidates"][0]  # type: ignore[index]

    first["candidates"].append({"changed": True})  # type: ignore[union-attr]
    first["candidates"][0]["equipment"].append(  # type: ignore[index]
        {
            "equipment_id": "changed",
            "part": "head",
            "series_skill_id": None,
            "group_skill_id": None,
        },
    )

    assert second == build_candidate_search_result_to_response(result=result)


def test_build_candidate_search_result_to_response_does_not_mutate_result() -> None:
    result = BuildCandidateSearchResult(
        candidates=(candidate(placements=(placement(),)),),
        total_count=1,
        truncated=False,
    )
    before = result

    build_candidate_search_result_to_response(result=result)

    assert result == before


def test_build_candidate_search_result_to_response_requires_keyword_argument() -> None:
    signature = inspect.signature(build_candidate_search_result_to_response)

    assert signature.parameters["result"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        build_candidate_search_result_to_response(
            BuildCandidateSearchResult(
                candidates=(),
                total_count=0,
                truncated=False,
            ),
        )  # type: ignore[call-arg]


@pytest.mark.parametrize("invalid_result", ["result", {}, None])
def test_build_candidate_search_result_to_response_rejects_invalid_result(
    invalid_result: object,
) -> None:
    with pytest.raises(TypeError, match="result"):
        build_candidate_search_result_to_response(
            result=invalid_result,  # type: ignore[arg-type]
        )


def test_build_candidate_search_result_to_response_public_import() -> None:
    from mhwilds_skill_sim.api import (
        build_candidate_search_result_to_response as exported_function,
    )

    assert exported_function is build_candidate_search_result_to_response


def test_api_all_matches_specification() -> None:
    import mhwilds_skill_sim.api as api

    assert api.__all__ == [
        "SearchRequest",
        "app",
        "build_candidate_search_result_to_response",
        "build_candidate_to_response",
        "create_app",
        "decode_search_request_payload",
        "search_catalog_build_candidates_from_payload",
    ]


def test_search_response_scope_regression() -> None:
    import mhwilds_skill_sim.api as api
    import mhwilds_skill_sim.api.search_response as search_response

    for name in ("SearchRequest", "SolverResult", "BuildResult"):
        assert not hasattr(search_response, name)

    for name in ("SolverResult", "BuildResult"):
        assert not hasattr(api, name)

    source = Path(search_response.__file__).read_text(encoding="utf-8")

    assert "fastapi" not in source.lower()
    assert "pydantic" not in source.lower()
    assert "router" not in source.lower()
