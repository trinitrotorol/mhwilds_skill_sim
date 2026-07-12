from __future__ import annotations

import copy
import inspect
import json
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path

import pytest

import mhwilds_skill_sim.api as api
import mhwilds_skill_sim.api.search_service as search_service
from mhwilds_skill_sim.api.search_request import decode_search_request_payload
from mhwilds_skill_sim.api.search_response import (
    build_candidate_search_result_to_response,
)
from mhwilds_skill_sim.api.search_service import (
    search_catalog_build_candidates_from_payload,
)
from mhwilds_skill_sim.catalog.loader import load_catalog
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.solver.search_result import (
    search_limited_catalog_build_candidates_by_skill_requirements,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"

EXPECTED_API_ALL = [
    "SearchRequest",
    "app",
    "build_candidate_search_result_to_response",
    "build_candidate_to_response",
    "create_app",
    "decode_search_request_payload",
    "search_catalog_build_candidates_from_payload",
]


class CatalogSubclass(Catalog):
    pass


def empty_catalog() -> Catalog:
    return Catalog(schema_version=1, equipment=(), decorations=())


def tiny_catalog() -> Catalog:
    return load_catalog(path=FIXTURE_PATH)


def equipment_definition(
    *,
    equipment_id: str,
    part: EquipmentPart,
    display_name: str,
    weapon_kind: WeaponKind | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=(),
        slots=(),
        display_name=display_name,
        weapon_kind=weapon_kind,
    )


def weapon_kind_catalog() -> Catalog:
    equipment = (
        equipment_definition(
            equipment_id="equipment:great-sword:first",
            part=EquipmentPart.WEAPON,
            display_name="First Great Sword",
            weapon_kind=WeaponKind.GREAT_SWORD,
        ),
        equipment_definition(
            equipment_id="equipment:bow",
            part=EquipmentPart.WEAPON,
            display_name="Test Bow",
            weapon_kind=WeaponKind.BOW,
        ),
        equipment_definition(
            equipment_id="equipment:great-sword:second",
            part=EquipmentPart.WEAPON,
            display_name="Second Great Sword",
            weapon_kind=WeaponKind.GREAT_SWORD,
        ),
        *(
            equipment_definition(
                equipment_id=f"equipment:{part.value}",
                part=part,
                display_name=f"Test {part.value}",
            )
            for part in (
                EquipmentPart.HEAD,
                EquipmentPart.CHEST,
                EquipmentPart.ARMS,
                EquipmentPart.WAIST,
                EquipmentPart.LEGS,
                EquipmentPart.CHARM,
            )
        ),
    )
    return Catalog(schema_version=1, equipment=equipment, decorations=())


def payload(
    *,
    requirements: list[dict[str, object]] | None = None,
    max_results: int = 10,
) -> dict[str, object]:
    return {
        "requirements": [] if requirements is None else requirements,
        "max_results": max_results,
    }


def requirement(skill_id: str, min_level: int) -> dict[str, object]:
    return {"skill_id": skill_id, "min_level": min_level}


def expected_response(
    *,
    catalog: Catalog,
    payload_value: object,
) -> dict[str, object]:
    request = decode_search_request_payload(payload=payload_value)
    result = search_limited_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=request.requirements,
        max_results=request.max_results,
        weapon_kind=request.weapon_kind,
    )
    return build_candidate_search_result_to_response(result=result)


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


def response_candidate_skill_levels(candidate: dict[str, object]) -> dict[str, int]:
    skill_levels = candidate["skill_levels"]
    assert isinstance(skill_levels, list)
    return {
        skill_level["skill_id"]: skill_level["level"] for skill_level in skill_levels
    }


def response_candidate_equipment_by_part(
    candidate: dict[str, object],
    part: str,
) -> dict[str, object]:
    equipment = candidate["equipment"]
    assert isinstance(equipment, list)
    return next(item for item in equipment if item["part"] == part)


def test_empty_catalog_and_empty_requirements_return_response_dict() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=empty_catalog(),
        payload=payload(),
    )

    assert response == {
        "candidates": [],
        "total_count": 0,
        "truncated": False,
    }


def test_weapon_kind_payload_filters_candidates_and_preserves_non_weapons() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=weapon_kind_catalog(),
        payload={
            "requirements": [],
            "max_results": 10,
            "weapon_kind": "great-sword",
        },
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert response["total_count"] == 2
    assert response["truncated"] is False
    assert [
        response_candidate_equipment_by_part(candidate, "weapon")["equipment_id"]
        for candidate in candidates
    ] == [
        "equipment:great-sword:first",
        "equipment:great-sword:second",
    ]
    assert all(
        response_candidate_equipment_by_part(candidate, "weapon")["weapon_kind"]
        == "great-sword"
        for candidate in candidates
    )
    assert all(
        equipment["weapon_kind"] is None
        for candidate in candidates
        for equipment in candidate["equipment"]  # type: ignore[union-attr]
        if equipment["part"] != "weapon"
    )
    assert (
        response_candidate_equipment_by_part(candidates[0], "weapon")["display_name"]
        == "First Great Sword"
    )
    json.dumps(response)


def test_weapon_kind_filtering_precedes_total_count_and_truncation() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=weapon_kind_catalog(),
        payload={
            "requirements": [],
            "max_results": 1,
            "weapon_kind": "great-sword",
        },
    )

    assert len(response["candidates"]) == 1  # type: ignore[arg-type]
    assert response["total_count"] == 2
    assert response["truncated"] is True


def test_weapon_kind_with_no_matching_weapon_returns_empty_result() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=weapon_kind_catalog(),
        payload={
            "requirements": [],
            "max_results": 10,
            "weapon_kind": "hammer",
        },
    )

    assert response == {
        "candidates": [],
        "total_count": 0,
        "truncated": False,
    }


def test_omitted_and_null_weapon_kind_preserve_default_behavior() -> None:
    catalog = weapon_kind_catalog()
    omitted_response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload={"requirements": [], "max_results": 10},
    )
    null_response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload={
            "requirements": [],
            "max_results": 10,
            "weapon_kind": None,
        },
    )

    assert omitted_response == null_response
    assert omitted_response["total_count"] == 3


def test_tiny_catalog_and_empty_requirements_return_response_dict() -> None:
    catalog = tiny_catalog()
    payload_value = payload(max_results=2)

    response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert response == expected_response(catalog=catalog, payload_value=payload_value)
    assert len(response["candidates"]) == 2  # type: ignore[arg-type]
    assert response["total_count"] > 2  # type: ignore[operator]
    assert response["truncated"] is True


def test_tiny_catalog_handles_equipment_skill_requirement_payload() -> None:
    catalog = tiny_catalog()
    payload_value = payload(
        requirements=[requirement("skill:attack-boost", 3)],
        max_results=3,
    )

    response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert response == expected_response(catalog=catalog, payload_value=payload_value)
    assert len(response["candidates"]) == 3  # type: ignore[arg-type]
    assert response["total_count"] >= 3  # type: ignore[operator]


def test_tiny_catalog_handles_decoration_skill_requirement_payload() -> None:
    catalog = tiny_catalog()
    payload_value = payload(
        requirements=[requirement("skill:weakness-exploit", 3)],
        max_results=5,
    )

    response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert response == expected_response(catalog=catalog, payload_value=payload_value)
    assert len(response["candidates"]) == 5  # type: ignore[arg-type]
    assert response["total_count"] >= 5  # type: ignore[operator]


def test_tiny_catalog_handles_series_bonus_requirement_payload() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement("skill:fixture-series-bonus", 2)],
            max_results=3,
        ),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert candidates
    assert all(
        response_candidate_skill_levels(candidate)["skill:fixture-series-bonus"] >= 2
        for candidate in candidates
    )
    assert all(
        response_candidate_equipment_by_part(candidate, "weapon")["series_skill_id"]
        == "skill:fixture-series-bonus"
        for candidate in candidates
    )


def test_tiny_catalog_handles_group_bonus_requirement_payload() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement("skill:fixture-group-bonus", 1)],
            max_results=3,
        ),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert candidates
    assert all(
        response_candidate_skill_levels(candidate)["skill:fixture-group-bonus"] >= 1
        for candidate in candidates
    )
    assert all(
        response_candidate_equipment_by_part(candidate, "weapon")["group_skill_id"]
        == "skill:fixture-group-bonus"
        for candidate in candidates
    )


@pytest.mark.parametrize(
    ("skill_id", "min_level"),
    [
        ("skill:fixture-series-bonus", 2),
        ("skill:fixture-group-bonus", 1),
    ],
)
def test_bonus_requirements_include_both_head_routes_after_artian_assignment(
    skill_id: str,
    min_level: int,
) -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement(skill_id, min_level)],
            max_results=99999,
        ),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert {
        response_candidate_equipment_by_part(candidate, "head")["equipment_id"]
        for candidate in candidates
    } == {
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
    }


def test_empty_requirement_response_exposes_resolved_artian_memberships() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(max_results=1),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    weapon = response_candidate_equipment_by_part(candidates[0], "weapon")
    assert weapon["equipment_id"] == "fixture:weapon:training-blade"
    assert weapon["series_skill_id"] == "skill:fixture-series-bonus"
    assert weapon["group_skill_id"] == "skill:fixture-group-bonus"
    json.dumps(response)


def test_impossible_bonus_level_returns_zero_candidates() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement("skill:fixture-series-bonus", 3)],
            max_results=10,
        ),
    )

    assert response == {
        "candidates": [],
        "total_count": 0,
        "truncated": False,
    }


def test_bonus_requirement_preserves_max_results_and_truncation() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement("skill:fixture-series-bonus", 2)],
            max_results=1,
        ),
    )

    assert len(response["candidates"]) == 1  # type: ignore[arg-type]
    assert response["total_count"] > 1  # type: ignore[operator]
    assert response["truncated"] is True
    json.dumps(response)


def test_unsatisfied_requirements_return_empty_candidates_response() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement("skill:does-not-exist", 1)],
            max_results=10,
        ),
    )

    assert response == {
        "candidates": [],
        "total_count": 0,
        "truncated": False,
    }


def test_zero_max_results_truncates_when_candidates_exist() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(max_results=0),
    )

    assert response["candidates"] == []
    assert response["total_count"] > 0  # type: ignore[operator]
    assert response["truncated"] is True


def test_one_max_result_returns_one_candidate() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(max_results=1),
    )

    assert len(response["candidates"]) == 1  # type: ignore[arg-type]
    assert response["total_count"] > 1  # type: ignore[operator]
    assert response["truncated"] is True


def test_large_max_results_returns_untruncated_response() -> None:
    catalog = tiny_catalog()
    payload_value = payload(max_results=99999)

    response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert response == expected_response(catalog=catalog, payload_value=payload_value)
    assert len(response["candidates"]) == response["total_count"]  # type: ignore[arg-type]
    assert response["truncated"] is False


def test_response_top_level_key_order() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(max_results=1),
    )

    assert list(response) == ["candidates", "total_count", "truncated"]


def test_response_is_json_serializable() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(max_results=1),
    )

    json.dumps(response)


def test_response_contains_no_internal_value_types() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(max_results=1),
    )

    assert not response_contains_unserializable_value(response)


def test_matches_direct_limited_solver_and_response_serializer() -> None:
    catalog = tiny_catalog()
    payload_value = payload(
        requirements=[requirement("skill:critical-eye", 3)],
        max_results=7,
    )

    response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert response == expected_response(catalog=catalog, payload_value=payload_value)


def test_function_requires_keyword_arguments() -> None:
    signature = inspect.signature(search_catalog_build_candidates_from_payload)

    assert signature.parameters["catalog"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["payload"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        search_catalog_build_candidates_from_payload(empty_catalog(), payload())  # type: ignore[call-arg]


def test_inputs_are_not_modified() -> None:
    catalog = tiny_catalog()
    payload_value = payload(
        requirements=[requirement("skill:attack-boost", 3)],
        max_results=2,
    )
    original_catalog = catalog
    original_payload = copy.deepcopy(payload_value)

    search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert catalog == original_catalog
    assert payload_value == original_payload


def test_public_import_from_api_package() -> None:
    from mhwilds_skill_sim.api import (
        search_catalog_build_candidates_from_payload as exported_function,
    )

    assert exported_function is search_catalog_build_candidates_from_payload


def test_existing_api_public_imports_are_preserved() -> None:
    assert api.SearchRequest is not None
    assert api.build_candidate_to_response is not None
    assert api.build_candidate_search_result_to_response is not None
    assert api.decode_search_request_payload is not None


def test_api_all_is_plain_list_in_expected_order() -> None:
    assert type(api.__all__) is list
    assert api.__all__ == EXPECTED_API_ALL


@pytest.mark.parametrize("catalog", ["catalog", {}, None])
def test_rejects_invalid_catalog_type(catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        search_catalog_build_candidates_from_payload(
            catalog=catalog,  # type: ignore[arg-type]
            payload=payload(),
        )


def test_accepts_catalog_subclass() -> None:
    catalog = CatalogSubclass(schema_version=1, equipment=(), decorations=())

    response = search_catalog_build_candidates_from_payload(
        catalog=catalog,
        payload=payload(),
    )

    assert response == {
        "candidates": [],
        "total_count": 0,
        "truncated": False,
    }


@pytest.mark.parametrize("payload_value", [None, "payload", []])
def test_propagates_invalid_payload_type_error(payload_value: object) -> None:
    with pytest.raises(TypeError, match="payload"):
        search_catalog_build_candidates_from_payload(
            catalog=empty_catalog(),
            payload=payload_value,
        )


def test_propagates_payload_root_key_value_error() -> None:
    with pytest.raises(ValueError, match="requirements.*max_results"):
        search_catalog_build_candidates_from_payload(
            catalog=empty_catalog(),
            payload={},
        )


def test_propagates_non_list_requirements_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_build_candidates_from_payload(
            catalog=empty_catalog(),
            payload={"requirements": (), "max_results": 1},
        )


@pytest.mark.parametrize(
    ("payload_value", "expected_error", "expected_message"),
    [
        (
            {"requirements": [None], "max_results": 1},
            TypeError,
            r"requirements\[0\]",
        ),
        (
            {
                "requirements": [
                    {"skill_id": "skill:attack-boost"},
                ],
                "max_results": 1,
            },
            ValueError,
            r"requirements\[0\].*min_level",
        ),
    ],
)
def test_propagates_invalid_requirement_item_errors(
    payload_value: object,
    expected_error: type[Exception],
    expected_message: str,
) -> None:
    with pytest.raises(expected_error, match=expected_message):
        search_catalog_build_candidates_from_payload(
            catalog=empty_catalog(),
            payload=payload_value,
        )


@pytest.mark.parametrize("max_results", [True, 1.5, "1", None])
def test_propagates_invalid_max_results_type_error(max_results: object) -> None:
    with pytest.raises(TypeError, match="max_results"):
        search_catalog_build_candidates_from_payload(
            catalog=empty_catalog(),
            payload={"requirements": [], "max_results": max_results},
        )


def test_propagates_invalid_max_results_value_error() -> None:
    with pytest.raises(ValueError, match="max_results"):
        search_catalog_build_candidates_from_payload(
            catalog=empty_catalog(),
            payload=payload(max_results=-1),
        )


@pytest.mark.parametrize(
    ("weapon_kind", "expected_error"),
    [
        ("Great-Sword", ValueError),
        ("great-sword ", ValueError),
        ("unknown", ValueError),
        (1, TypeError),
    ],
)
def test_propagates_invalid_weapon_kind_error(
    weapon_kind: object,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error, match="weapon_kind"):
        search_catalog_build_candidates_from_payload(
            catalog=weapon_kind_catalog(),
            payload={
                "requirements": [],
                "max_results": 1,
                "weapon_kind": weapon_kind,
            },
        )


def test_propagates_duplicate_requirement_skill_id_value_error() -> None:
    with pytest.raises(ValueError, match="requirements"):
        search_catalog_build_candidates_from_payload(
            catalog=empty_catalog(),
            payload=payload(
                requirements=[
                    requirement("skill:attack-boost", 1),
                    requirement("skill:attack-boost", 2),
                ],
            ),
        )


def test_scope_uses_prebuilt_catalog_without_loading_catalog() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=empty_catalog(),
        payload=payload(),
    )

    assert response["total_count"] == 0


def test_search_service_scope_regression() -> None:
    source = Path(search_service.__file__).read_text(encoding="utf-8")
    lowered_source = source.lower()

    assert "load_catalog" not in source
    assert "from mhwilds_skill_sim.api import" not in source
    assert "from mhwilds_skill_sim.catalog import" not in source
    assert "from mhwilds_skill_sim.solver import" not in source
    assert "fastapi" not in lowered_source
    assert "pydantic" not in lowered_source
    assert "router" not in lowered_source
    assert "endpoint" not in lowered_source
    assert "SearchRequest" not in source
    assert "SolverResult" not in source
    assert "BuildResult" not in source
    assert "ranking" not in lowered_source
    assert "score" not in lowered_source
    assert "topk" not in lowered_source
    assert "top_k" not in lowered_source
    assert "print(" not in source


def test_search_service_module_adds_no_result_or_request_types() -> None:
    for name in ("SearchRequest", "SolverResult", "BuildResult"):
        assert not hasattr(search_service, name)


def test_generated_weapon_skill_payload_exposes_charm_and_artian_details() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement("skill:fixture-weapon-technique", 1)],
            max_results=1,
        ),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 1
    candidate = candidates[0]
    charm = response_candidate_equipment_by_part(candidate, "charm")
    weapon = response_candidate_equipment_by_part(candidate, "weapon")

    assert charm["equipment_id"].startswith("generated:appraisal-charm:")  # type: ignore[union-attr]
    assert charm["skills"] == [
        {"skill_id": "skill:fixture-weapon-technique", "level": 1},
        {"skill_id": "skill:attack-boost", "level": 1},
        {"skill_id": "skill:weakness-exploit", "level": 1},
    ]
    assert charm["slots"] == [
        {"kind": "weapon", "level": 1},
        {"kind": "armor", "level": 1},
        {"kind": "armor", "level": 1},
    ]
    assert weapon["series_skill_id"] == "skill:fixture-series-bonus"
    assert weapon["group_skill_id"] == "skill:fixture-group-bonus"
    assert response["total_count"] > 1  # type: ignore[operator]
    assert response["truncated"] is True
    json.dumps(response)
    assert not response_contains_unserializable_value(response)


def test_duplicate_skill_aggregation_route_is_visible_through_api() -> None:
    response = search_catalog_build_candidates_from_payload(
        catalog=tiny_catalog(),
        payload=payload(
            requirements=[requirement("skill:attack-boost", 5)],
            max_results=1000,
        ),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    aggregated_charms: list[dict[str, object]] = []
    for candidate in candidates:
        charm = response_candidate_equipment_by_part(candidate, "charm")
        charm_id = charm["equipment_id"]
        charm_skills = charm["skills"]
        assert isinstance(charm_id, str)
        assert isinstance(charm_skills, list)
        levels = {skill["skill_id"]: skill["level"] for skill in charm_skills}
        if (
            charm_id.startswith("generated:appraisal-charm:")
            and levels.get("skill:attack-boost") == 3
        ):
            aggregated_charms.append(charm)

    assert aggregated_charms
    assert all(
        charm["skills"][0]  # type: ignore[index]
        == {"skill_id": "skill:attack-boost", "level": 3}
        for charm in aggregated_charms
    )
    assert len(candidates) == 1000
    assert response["total_count"] > len(candidates)  # type: ignore[operator]
    assert response["truncated"] is True
    json.dumps(response)
