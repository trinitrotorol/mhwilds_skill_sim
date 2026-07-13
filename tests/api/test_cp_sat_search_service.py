from __future__ import annotations

import copy
import importlib
import inspect
import json

import pytest

import mhwilds_skill_sim.api as api_package
import mhwilds_skill_sim.api.search_service as search_service_module
import mhwilds_skill_sim.solver.build as build_module
import mhwilds_skill_sim.solver.catalog_search as catalog_search_module
import mhwilds_skill_sim.solver.decoration as decoration_solver_module
import mhwilds_skill_sim.solver.equipment as equipment_solver_module
from mhwilds_skill_sim.api.search_request import SearchRequest
from mhwilds_skill_sim.api.search_service import (
    search_catalog_build_candidates_with_cp_sat_from_payload,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.cp_sat_search import CpSatBuildSearchResult
from mhwilds_skill_sim.solver.requirements import SkillRequirement


REQUIRED_PARTS = tuple(EquipmentPart)


class CatalogSubclass(Catalog):
    pass


def contribution(skill_id: str, level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id=skill_id, level=level)


def equipment_item(
    part: EquipmentPart,
    equipment_id: str | None = None,
    *,
    skills: tuple[SkillContribution, ...] = (),
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
    display_name: str | None = None,
    weapon_kind: WeaponKind | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=(),
        allows_series_skill_assignment=allows_series_skill_assignment,
        allows_group_skill_assignment=allows_group_skill_assignment,
        display_name=display_name,
        weapon_kind=weapon_kind,
    )


def complete_equipment(
    *,
    replacements: dict[EquipmentPart, EquipmentDefinition] | None = None,
) -> tuple[EquipmentDefinition, ...]:
    selected_replacements = replacements or {}
    return tuple(
        selected_replacements.get(part, equipment_item(part)) for part in REQUIRED_PARTS
    )


def small_catalog(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    skills: tuple[SkillDefinition, ...] = (),
    appraisal_groups: tuple[AppraisalCharmSkillGroupDefinition, ...] = (),
    appraisal_patterns: tuple[AppraisalCharmPatternDefinition, ...] = (),
) -> Catalog:
    return Catalog(
        schema_version=1,
        equipment=complete_equipment() if equipment is None else equipment,
        decorations=(),
        skills=skills,
        appraisal_charm_skill_groups=appraisal_groups,
        appraisal_charm_patterns=appraisal_patterns,
    )


def normal_skill(
    skill_id: str, *, kind: SkillKind = SkillKind.ARMOR
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=(SkillRankDefinition(level=1, required_pieces=None),),
    )


def bonus_skill(skill_id: str, *, kind: SkillKind) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=(SkillRankDefinition(level=1, required_pieces=1),),
    )


def payload(
    *,
    requirements: list[dict[str, object]] | None = None,
    max_results: int = 10,
    weapon_kind: object | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "requirements": [] if requirements is None else requirements,
        "max_results": max_results,
    }
    if weapon_kind is not None:
        value["weapon_kind"] = weapon_kind
    return value


def requirement_payload(skill_id: str, level: int = 1) -> dict[str, object]:
    return {"skill_id": skill_id, "min_level": level}


def equipment_response_by_part(
    candidate: dict[str, object],
    part: EquipmentPart,
) -> dict[str, object]:
    equipment = candidate["equipment"]
    assert isinstance(equipment, list)
    return next(item for item in equipment if item["part"] == part.value)


def test_empty_catalog_returns_exhausted_empty_response() -> None:
    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=Catalog(schema_version=1, equipment=(), decorations=()),
        payload=payload(),
    )

    assert response == {
        "candidates": [],
        "exhausted": True,
        "timed_out": False,
    }


def test_catalog_subclass_is_accepted() -> None:
    catalog = CatalogSubclass(schema_version=1, equipment=(), decorations=())

    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload(),
    )

    assert response == {
        "candidates": [],
        "exhausted": True,
        "timed_out": False,
    }


def test_one_equipment_selection_is_returned_and_proven_exhausted() -> None:
    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(),
        payload=payload(max_results=1),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 1
    assert response["exhausted"] is True
    assert response["timed_out"] is False
    assert list(response) == ["candidates", "exhausted", "timed_out"]
    assert [item["part"] for item in candidates[0]["equipment"]] == [
        part.value for part in REQUIRED_PARTS
    ]
    json.dumps(response)


def test_more_equipment_selections_than_limit_reports_non_exhausted() -> None:
    equipment = complete_equipment() + (
        equipment_item(EquipmentPart.HEAD, "equipment:head:second"),
        equipment_item(EquipmentPart.HEAD, "equipment:head:third"),
    )

    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(equipment=equipment),
        payload=payload(max_results=2),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 2
    assert response["exhausted"] is False
    assert response["timed_out"] is False
    assert (
        len(
            {
                equipment_response_by_part(candidate, EquipmentPart.HEAD)[
                    "equipment_id"
                ]
                for candidate in candidates
            }
        )
        == 2
    )


def test_zero_max_results_probes_existing_solution_without_returning_it() -> None:
    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(),
        payload=payload(max_results=0),
    )

    assert response == {
        "candidates": [],
        "exhausted": False,
        "timed_out": False,
    }


def test_composition_reuses_decoder_and_serializer_and_forwards_solver_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = small_catalog()
    payload_value = payload(
        requirements=[requirement_payload("skill:required", 2)],
        max_results=4,
        weapon_kind="bow",
    )
    solver_result = CpSatBuildSearchResult(
        candidates=(),
        exhausted=True,
        timed_out=False,
    )
    serialized_response: dict[str, object] = {"serialized": True}
    decoded_calls: list[object] = []
    solver_calls: list[dict[str, object]] = []
    serializer_calls: list[CpSatBuildSearchResult] = []
    original_decoder = search_service_module.decode_search_request_payload

    def recording_decoder(*, payload: object) -> SearchRequest:
        decoded_calls.append(payload)
        return original_decoder(payload=payload)

    def fake_solver(
        *,
        catalog: Catalog,
        requirements: tuple[SkillRequirement, ...],
        max_results: int,
        weapon_kind: WeaponKind | None,
        timeout_seconds: float,
    ) -> CpSatBuildSearchResult:
        solver_calls.append(
            {
                "catalog": catalog,
                "requirements": requirements,
                "max_results": max_results,
                "weapon_kind": weapon_kind,
                "timeout_seconds": timeout_seconds,
            }
        )
        return solver_result

    def fake_serializer(
        *,
        result: CpSatBuildSearchResult,
    ) -> dict[str, object]:
        serializer_calls.append(result)
        return serialized_response

    monkeypatch.setattr(
        search_service_module,
        "decode_search_request_payload",
        recording_decoder,
    )
    monkeypatch.setattr(
        search_service_module,
        "search_catalog_build_candidates_with_cp_sat",
        fake_solver,
    )
    monkeypatch.setattr(
        search_service_module,
        "build_cp_sat_search_result_to_response",
        fake_serializer,
    )

    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert response is serialized_response
    assert decoded_calls == [payload_value]
    assert decoded_calls[0] is payload_value
    assert len(solver_calls) == 1
    assert solver_calls[0]["catalog"] is catalog
    assert solver_calls[0]["requirements"] == (
        SkillRequirement(skill_id="skill:required", min_level=2),
    )
    assert solver_calls[0]["max_results"] == 4
    assert solver_calls[0]["weapon_kind"] is WeaponKind.BOW
    assert solver_calls[0]["timeout_seconds"] == 10.0
    assert serializer_calls == [solver_result]


def test_timeout_result_preserves_serialized_partial_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    partial_candidate = BuildCandidate(
        equipment=(
            equipment_item(
                EquipmentPart.WEAPON,
                "equipment:weapon:partial",
                display_name="Partial Bow",
                weapon_kind=WeaponKind.BOW,
            ),
        ),
        placements=(),
        skill_levels=(("skill:partial", 1),),
    )
    timeout_result = CpSatBuildSearchResult(
        candidates=(partial_candidate,),
        exhausted=False,
        timed_out=True,
    )

    def fake_solver(**_kwargs: object) -> CpSatBuildSearchResult:
        return timeout_result

    monkeypatch.setattr(
        search_service_module,
        "search_catalog_build_candidates_with_cp_sat",
        fake_solver,
    )

    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(),
        payload=payload(max_results=3),
    )

    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 1
    assert candidates[0]["equipment"] == [
        {
            "equipment_id": "equipment:weapon:partial",
            "display_name": "Partial Bow",
            "part": "weapon",
            "weapon_kind": "bow",
            "series_skill_id": None,
            "group_skill_id": None,
            "series_skill_ids": [],
            "group_skill_ids": [],
            "skills": [],
            "slots": [],
        }
    ]
    assert candidates[0]["skill_levels"] == [{"skill_id": "skill:partial", "level": 1}]
    assert response["exhausted"] is False
    assert response["timed_out"] is True
    json.dumps(response)


def test_generated_appraisal_charm_and_resolved_artian_reach_http_shape() -> None:
    appraisal_skill_id = "skill:appraisal-technique"
    series_skill_id = "skill:artian-series"
    group_skill_id = "skill:artian-group"
    artian = equipment_item(
        EquipmentPart.WEAPON,
        "equipment:weapon:artian",
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
        display_name="Test Artian",
        weapon_kind=WeaponKind.GREAT_SWORD,
    )
    appraisal_group = AppraisalCharmSkillGroupDefinition(
        group_id="appraisal-group:technique",
        skills=(contribution(appraisal_skill_id),),
    )
    appraisal_pattern = AppraisalCharmPatternDefinition(
        pattern_id="appraisal-pattern:technique",
        rarity=8,
        skill_group_ids=(appraisal_group.group_id,),
        slots=(),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.WEAPON: artian},
        ),
        skills=(
            bonus_skill(series_skill_id, kind=SkillKind.SERIES),
            bonus_skill(group_skill_id, kind=SkillKind.GROUP),
            normal_skill(appraisal_skill_id, kind=SkillKind.WEAPON),
        ),
        appraisal_groups=(appraisal_group,),
        appraisal_patterns=(appraisal_pattern,),
    )

    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload(
            requirements=[requirement_payload(appraisal_skill_id)],
            max_results=1,
            weapon_kind="great-sword",
        ),
    )

    assert list(response) == ["candidates", "exhausted", "timed_out"]
    candidates = response["candidates"]
    assert isinstance(candidates, list)
    assert len(candidates) == 1
    candidate = candidates[0]
    weapon = equipment_response_by_part(candidate, EquipmentPart.WEAPON)
    charm = equipment_response_by_part(candidate, EquipmentPart.CHARM)
    assert weapon["equipment_id"] == artian.equipment_id
    assert weapon["display_name"] == "Test Artian"
    assert weapon["weapon_kind"] == "great-sword"
    assert weapon["series_skill_id"] == series_skill_id
    assert weapon["group_skill_id"] == group_skill_id
    assert weapon["series_skill_ids"] == [series_skill_id]
    assert weapon["group_skill_ids"] == [group_skill_id]
    assert charm["equipment_id"].startswith("generated:appraisal-charm:")
    assert charm["skills"] == [{"skill_id": appraisal_skill_id, "level": 1}]
    assert response["exhausted"] is True
    assert response["timed_out"] is False
    assert "total_count" not in response
    assert "truncated" not in response
    json.dumps(response)


@pytest.mark.parametrize("invalid_catalog", [None, object(), {}, "catalog"])
def test_invalid_catalog_type_is_rejected(invalid_catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=invalid_catalog,  # type: ignore[arg-type]
            payload=payload(),
        )


@pytest.mark.parametrize("invalid_payload", [None, "payload", []])
def test_invalid_payload_type_error_is_propagated(invalid_payload: object) -> None:
    with pytest.raises(TypeError, match="payload"):
        search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=invalid_payload,
        )


def test_invalid_payload_shape_error_is_propagated() -> None:
    with pytest.raises(ValueError, match="requirements.*max_results"):
        search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload={},
        )


def test_duplicate_requirement_error_is_propagated() -> None:
    with pytest.raises(ValueError, match="requirements"):
        search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=payload(
                requirements=[
                    requirement_payload("skill:duplicate", 1),
                    requirement_payload("skill:duplicate", 2),
                ]
            ),
        )


@pytest.mark.parametrize("invalid_max_results", [True, 1.5, "1", None])
def test_invalid_max_results_type_error_is_propagated(
    invalid_max_results: object,
) -> None:
    payload_value = {
        "requirements": [],
        "max_results": invalid_max_results,
    }

    with pytest.raises(TypeError, match="max_results"):
        search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=payload_value,
        )


def test_negative_max_results_error_is_propagated() -> None:
    with pytest.raises(ValueError, match="max_results"):
        search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=payload(max_results=-1),
        )


@pytest.mark.parametrize(
    ("invalid_weapon_kind", "expected_error"),
    [
        ("Bow", ValueError),
        ("bow ", ValueError),
        ("unknown", ValueError),
        (1, TypeError),
    ],
)
def test_invalid_weapon_kind_error_is_propagated(
    invalid_weapon_kind: object,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error, match="weapon_kind"):
        search_catalog_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=payload(weapon_kind=invalid_weapon_kind),
        )


def test_catalog_and_payload_are_not_modified() -> None:
    skill_id = "skill:fixed"
    fixed_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:fixed",
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: fixed_head},
        )
    )
    payload_value = payload(
        requirements=[requirement_payload(skill_id)],
        max_results=1,
    )
    catalog_before = copy.deepcopy(catalog)
    payload_before = copy.deepcopy(payload_value)
    equipment_before = catalog.equipment

    search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert catalog == catalog_before
    assert catalog.equipment is equipment_before
    assert payload_value == payload_before


def test_cp_sat_service_does_not_call_exhaustive_search_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("CP-SAT service must not use exhaustive search")

    monkeypatch.setattr(
        search_service_module,
        "search_catalog_build_candidates_from_payload",
        fail,
    )
    monkeypatch.setattr(
        search_service_module,
        "search_limited_catalog_build_candidates_by_skill_requirements",
        fail,
    )
    monkeypatch.setattr(build_module, "enumerate_build_candidates", fail)
    monkeypatch.setattr(
        catalog_search_module,
        "search_catalog_build_candidates_by_skill_requirements",
        fail,
    )
    monkeypatch.setattr(
        equipment_solver_module,
        "enumerate_equipment_selections",
        fail,
    )
    monkeypatch.setattr(
        decoration_solver_module,
        "enumerate_decoration_placement_combinations",
        fail,
    )

    response = search_catalog_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(),
        payload=payload(max_results=1),
    )

    assert len(response["candidates"]) == 1  # type: ignore[arg-type]


def test_function_has_exact_keyword_only_signature() -> None:
    parameters = inspect.signature(
        search_catalog_build_candidates_with_cp_sat_from_payload,
    ).parameters

    assert tuple(parameters) == ("catalog", "payload")
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in parameters.values()
    )

    with pytest.raises(TypeError):
        search_catalog_build_candidates_with_cp_sat_from_payload(  # type: ignore[misc]
            small_catalog(),
            payload(),
        )


def test_function_is_directly_importable_but_not_exported_by_api_package() -> None:
    imported_module = importlib.import_module("mhwilds_skill_sim.api.search_service")
    function_name = "search_catalog_build_candidates_with_cp_sat_from_payload"

    assert (
        getattr(imported_module, function_name)
        is search_catalog_build_candidates_with_cp_sat_from_payload
    )
    assert function_name not in api_package.__all__
    assert not hasattr(api_package, function_name)
