from __future__ import annotations

import copy
import importlib
import inspect
import json
from dataclasses import is_dataclass
from enum import Enum

import pytest

import mhwilds_skill_sim.api as api
import mhwilds_skill_sim.api.search_response as search_response
from mhwilds_skill_sim.api.search_response import (
    build_candidate_search_result_to_response,
    build_candidate_to_response,
    build_cp_sat_search_result_to_response,
)
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.cp_sat_search import CpSatBuildSearchResult
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


def equipment_definition(
    part: EquipmentPart,
    equipment_id: str,
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
    part: EquipmentPart,
    equipment_id: str,
) -> BuildCandidate:
    return BuildCandidate(
        equipment=(equipment_definition(part, equipment_id),),
        placements=(),
        skill_levels=(),
    )


def detailed_candidate() -> BuildCandidate:
    equipment_id = "equipment:weapon:test"
    return BuildCandidate(
        equipment=(
            equipment_definition(
                EquipmentPart.WEAPON,
                equipment_id,
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


def test_build_cp_sat_search_result_to_response_converts_empty_result() -> None:
    response = build_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(),
            exhausted=True,
            timed_out=False,
        ),
    )

    assert response == {
        "candidates": [],
        "exhausted": True,
        "timed_out": False,
    }


def test_build_cp_sat_search_result_to_response_preserves_candidate_order() -> None:
    first = candidate(EquipmentPart.WEAPON, "equipment:weapon:first")
    second = candidate(EquipmentPart.HEAD, "equipment:head:second")

    response = build_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(first, second),
            exhausted=False,
            timed_out=False,
        ),
    )

    assert response["candidates"] == [
        build_candidate_to_response(candidate=first),
        build_candidate_to_response(candidate=second),
    ]


@pytest.mark.parametrize(
    ("exhausted", "timed_out"),
    [
        (True, False),
        (False, False),
        (False, True),
    ],
)
def test_build_cp_sat_search_result_to_response_preserves_search_state(
    exhausted: bool,
    timed_out: bool,
) -> None:
    response = build_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(),
            exhausted=exhausted,
            timed_out=timed_out,
        ),
    )

    assert response["exhausted"] is exhausted
    assert response["timed_out"] is timed_out


def test_build_cp_sat_search_result_to_response_has_exact_key_order() -> None:
    response = build_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(),
            exhausted=True,
            timed_out=False,
        ),
    )

    assert list(response) == ["candidates", "exhausted", "timed_out"]
    assert "total_count" not in response
    assert "truncated" not in response


def test_build_cp_sat_search_result_to_response_is_json_serializable() -> None:
    response = build_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(detailed_candidate(),),
            exhausted=False,
            timed_out=True,
        ),
    )

    json.dumps(response)
    assert not response_contains_unserializable_value(response)


def test_build_cp_sat_search_result_to_response_reuses_candidate_serializer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = candidate(EquipmentPart.WEAPON, "equipment:weapon:first")
    second = candidate(EquipmentPart.HEAD, "equipment:head:second")
    calls: list[BuildCandidate] = []

    def fake_candidate_serializer(*, candidate: BuildCandidate) -> dict[str, object]:
        calls.append(candidate)
        return {"equipment_id": candidate.equipment[0].equipment_id}

    monkeypatch.setattr(
        search_response,
        "build_candidate_to_response",
        fake_candidate_serializer,
    )

    response = build_cp_sat_search_result_to_response(
        result=CpSatBuildSearchResult(
            candidates=(first, second),
            exhausted=False,
            timed_out=False,
        ),
    )

    assert calls == [first, second]
    assert response["candidates"] == [
        {"equipment_id": "equipment:weapon:first"},
        {"equipment_id": "equipment:head:second"},
    ]


def test_build_cp_sat_search_result_to_response_returns_new_containers() -> None:
    result = CpSatBuildSearchResult(
        candidates=(detailed_candidate(),),
        exhausted=False,
        timed_out=True,
    )

    first = build_cp_sat_search_result_to_response(result=result)
    second = build_cp_sat_search_result_to_response(result=result)
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
    assert first_item["skills"] is not second_item["skills"]
    assert first_item["skills"][0] is not second_item["skills"][0]
    assert first_item["slots"] is not second_item["slots"]
    assert first_item["slots"][0] is not second_item["slots"][0]
    assert first_candidate["placements"] is not second_candidate["placements"]
    assert first_candidate["placements"][0] is not second_candidate["placements"][0]
    assert first_candidate["skill_levels"] is not second_candidate["skill_levels"]
    assert first_candidate["skill_levels"][0] is not second_candidate["skill_levels"][0]

    first_item["skills"].append({"skill_id": "changed", "level": 99})
    assert second == build_cp_sat_search_result_to_response(result=result)


def test_build_cp_sat_search_result_to_response_does_not_mutate_result() -> None:
    build = detailed_candidate()
    result = CpSatBuildSearchResult(
        candidates=(build,),
        exhausted=False,
        timed_out=True,
    )
    before = copy.deepcopy(result)

    build_cp_sat_search_result_to_response(result=result)

    assert result == before
    assert result.candidates[0] is build


def test_build_cp_sat_search_result_to_response_requires_keyword_argument() -> None:
    signature = inspect.signature(build_cp_sat_search_result_to_response)

    assert list(signature.parameters) == ["result"]
    assert signature.parameters["result"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        build_cp_sat_search_result_to_response(
            CpSatBuildSearchResult(
                candidates=(),
                exhausted=True,
                timed_out=False,
            ),
        )  # type: ignore[call-arg]


@pytest.mark.parametrize("invalid_result", ["result", {}, None])
def test_build_cp_sat_search_result_to_response_rejects_invalid_result(
    invalid_result: object,
) -> None:
    with pytest.raises(TypeError, match="result"):
        build_cp_sat_search_result_to_response(
            result=invalid_result,  # type: ignore[arg-type]
        )


def test_build_cp_sat_search_result_to_response_direct_module_import() -> None:
    imported_module = importlib.import_module(
        "mhwilds_skill_sim.api.search_response",
    )

    assert (
        imported_module.build_cp_sat_search_result_to_response
        is build_cp_sat_search_result_to_response
    )


def test_build_cp_sat_search_result_to_response_is_not_package_exported() -> None:
    assert "build_cp_sat_search_result_to_response" not in api.__all__
    assert not hasattr(api, "build_cp_sat_search_result_to_response")


def test_existing_serializers_and_public_exports_are_unchanged() -> None:
    assert api.__all__ == EXPECTED_API_ALL
    assert api.build_candidate_to_response is build_candidate_to_response
    assert (
        api.build_candidate_search_result_to_response
        is build_candidate_search_result_to_response
    )
