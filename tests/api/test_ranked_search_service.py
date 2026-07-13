from __future__ import annotations

import copy
import importlib
import inspect
import json

import pytest

import mhwilds_skill_sim.api as api_package
import mhwilds_skill_sim.api.search_service as search_service_module
from mhwilds_skill_sim.api.ranked_search_request import RankedSearchRequest
from mhwilds_skill_sim.api.search_service import (
    search_catalog_ranked_build_candidates_with_cp_sat_from_payload,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.cp_sat_search import CpSatBuildSearchResult
from mhwilds_skill_sim.solver.preferences import (
    SkillPreference,
    calculate_skill_preference_score,
)
from mhwilds_skill_sim.solver.requirements import SkillRequirement


EXPECTED_API_ALL = [
    "SearchRequest",
    "app",
    "build_candidate_search_result_to_response",
    "build_candidate_to_response",
    "create_app",
    "decode_search_request_payload",
    "search_catalog_build_candidates_from_payload",
]
REQUIRED_PARTS = tuple(EquipmentPart)


class CatalogSubclass(Catalog):
    pass


def contribution(skill_id: str, level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id=skill_id, level=level)


def slot(kind: DecorationKind, level: int = 1) -> DecorationSlot:
    return DecorationSlot(kind=kind, level=level)


def equipment_item(
    part: EquipmentPart,
    equipment_id: str | None = None,
    *,
    skills: tuple[SkillContribution, ...] = (),
    slots: tuple[DecorationSlot, ...] = (),
    weapon_kind: WeaponKind | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=slots,
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


def decoration(
    decoration_id: str,
    *,
    skills: tuple[SkillContribution, ...],
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=slot(DecorationKind.ARMOR),
        skills=skills,
    )


def small_catalog(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    decorations: tuple[DecorationDefinition, ...] = (),
) -> Catalog:
    return Catalog(
        schema_version=1,
        equipment=complete_equipment() if equipment is None else equipment,
        decorations=decorations,
    )


def requirement_payload(skill_id: str, level: int = 1) -> dict[str, object]:
    return {"skill_id": skill_id, "min_level": level}


def preference_payload(skill_id: str, level: int = 1) -> dict[str, object]:
    return {"skill_id": skill_id, "target_level": level}


def ranked_payload(
    *,
    requirements: list[dict[str, object]] | None = None,
    preferences: list[dict[str, object]] | None = None,
    max_results: int = 10,
    weapon_kind: str | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "requirements": [] if requirements is None else requirements,
        "preferences": [] if preferences is None else preferences,
        "max_results": max_results,
    }
    if weapon_kind is not None:
        value["weapon_kind"] = weapon_kind
    return value


def response_candidates(response: dict[str, object]) -> list[dict[str, object]]:
    candidates = response["candidates"]
    assert isinstance(candidates, list)
    return candidates


def selected_equipment_id(
    candidate: dict[str, object],
    part: EquipmentPart,
) -> str:
    equipment = candidate["equipment"]
    assert isinstance(equipment, list)
    selected = next(item for item in equipment if item["part"] == part.value)
    equipment_id = selected["equipment_id"]
    assert isinstance(equipment_id, str)
    return equipment_id


def test_function_has_exact_keyword_only_signature_and_rejects_positionals() -> None:
    parameters = inspect.signature(
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload,
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
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload(  # type: ignore[misc]
            small_catalog(),
            ranked_payload(),
        )


def test_function_is_directly_importable_but_not_package_exported() -> None:
    imported_module = importlib.import_module("mhwilds_skill_sim.api.search_service")
    function_name = "search_catalog_ranked_build_candidates_with_cp_sat_from_payload"

    assert (
        getattr(imported_module, function_name)
        is search_catalog_ranked_build_candidates_with_cp_sat_from_payload
    )
    assert api_package.__all__ == EXPECTED_API_ALL
    assert function_name not in api_package.__all__
    assert not hasattr(api_package, function_name)


def test_catalog_subclass_is_accepted() -> None:
    catalog = CatalogSubclass(schema_version=1, equipment=(), decorations=())

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=ranked_payload(
            preferences=[preference_payload("skill:unknown")],
        ),
    )

    assert response == {
        "candidates": [],
        "exhausted": True,
        "timed_out": False,
    }


@pytest.mark.parametrize("invalid_catalog", [None, object(), {}, "catalog", 0])
def test_invalid_catalog_is_rejected_before_request_decoding(
    monkeypatch: pytest.MonkeyPatch,
    invalid_catalog: object,
) -> None:
    def fail_decoder(**_kwargs: object) -> object:
        raise AssertionError("decoder must not run for an invalid Catalog")

    monkeypatch.setattr(
        search_service_module,
        "decode_ranked_search_request_payload",
        fail_decoder,
    )

    with pytest.raises(TypeError, match="catalog"):
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
            catalog=invalid_catalog,  # type: ignore[arg-type]
            payload=ranked_payload(),
        )


def test_composition_order_and_forwarded_identities_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = small_catalog()
    payload_value = object()
    requirements = (SkillRequirement("skill:required", 2),)
    preferences = (SkillPreference("skill:preferred", 3),)
    request = RankedSearchRequest(
        requirements=requirements,
        preferences=preferences,
        max_results=4,
        weapon_kind=WeaponKind.BOW,
    )
    solver_result = CpSatBuildSearchResult(
        candidates=(),
        exhausted=False,
        timed_out=True,
    )
    serialized: dict[str, object] = {"serialized": True}
    events: list[str] = []

    def fake_decoder(*, payload: object) -> RankedSearchRequest:
        events.append("decode")
        assert payload is payload_value
        return request

    def fake_solver(**kwargs: object) -> CpSatBuildSearchResult:
        events.append("solve")
        assert kwargs == {
            "catalog": catalog,
            "requirements": requirements,
            "preferences": preferences,
            "max_results": 4,
            "weapon_kind": WeaponKind.BOW,
            "timeout_seconds": 10.0,
        }
        assert kwargs["catalog"] is catalog
        assert kwargs["requirements"] is requirements
        assert kwargs["preferences"] is preferences
        return solver_result

    def fake_serializer(
        *,
        result: CpSatBuildSearchResult,
        preferences: tuple[SkillPreference, ...],
    ) -> dict[str, object]:
        events.append("serialize")
        assert result is solver_result
        assert preferences is request.preferences
        return serialized

    monkeypatch.setattr(
        search_service_module,
        "decode_ranked_search_request_payload",
        fake_decoder,
    )
    monkeypatch.setattr(
        search_service_module,
        "search_catalog_ranked_build_candidates_with_cp_sat",
        fake_solver,
    )
    monkeypatch.setattr(
        search_service_module,
        "build_ranked_cp_sat_search_result_to_response",
        fake_serializer,
    )

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert response is serialized
    assert events == ["decode", "solve", "serialize"]


def test_empty_catalog_and_empty_preferences_return_empty_response() -> None:
    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=Catalog(schema_version=1, equipment=(), decorations=()),
        payload=ranked_payload(),
    )

    assert response == {
        "candidates": [],
        "exhausted": True,
        "timed_out": False,
    }


def test_zero_max_results_returns_no_candidates_without_exhaustion() -> None:
    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(),
        payload=ranked_payload(
            preferences=[preference_payload("skill:preferred")],
            max_results=0,
        ),
    )

    assert response == {
        "candidates": [],
        "exhausted": False,
        "timed_out": False,
    }


def test_hard_requirement_excludes_a_higher_preference_score_candidate() -> None:
    required_id = "skill:required"
    preferred_id = "skill:preferred"
    invalid_high = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:invalid-high",
        skills=(contribution(preferred_id, 5),),
    )
    valid_lower = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:valid-lower",
        skills=(contribution(required_id), contribution(preferred_id)),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: invalid_high},
        )
        + (valid_lower,),
    )

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=ranked_payload(
            requirements=[requirement_payload(required_id)],
            preferences=[preference_payload(preferred_id, 5)],
            max_results=2,
        ),
    )

    candidates = response_candidates(response)
    assert len(candidates) == 1
    assert selected_equipment_id(candidates[0], EquipmentPart.HEAD) == (
        valid_lower.equipment_id
    )
    assert candidates[0]["preference_score"] == 1
    assert response["exhausted"] is True


def test_higher_preference_score_candidate_is_returned_first() -> None:
    skill_id = "skill:preferred"
    high = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:high",
        skills=(contribution(skill_id, 3),),
    )
    low = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:low",
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: high}) + (low,),
    )

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=ranked_payload(
            preferences=[preference_payload(skill_id, 3)],
            max_results=2,
        ),
    )

    candidates = response_candidates(response)
    assert [candidate["preference_score"] for candidate in candidates] == [3, 1]
    assert selected_equipment_id(candidates[0], EquipmentPart.HEAD) == high.equipment_id


def test_same_capped_score_prefers_fewer_decorations() -> None:
    skill_id = "skill:capped"
    fixed = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:fixed",
        skills=(contribution(skill_id, 4),),
    )
    decorated = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:decorated",
        slots=(slot(DecorationKind.ARMOR),),
    )
    definition = decoration(
        "decoration:capped",
        skills=(contribution(skill_id, 5),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: fixed})
        + (decorated,),
        decorations=(definition,),
    )

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=ranked_payload(
            preferences=[preference_payload(skill_id, 2)],
            max_results=2,
        ),
    )

    candidates = response_candidates(response)
    assert [candidate["preference_score"] for candidate in candidates] == [2, 2]
    assert [len(candidate["placements"]) for candidate in candidates] == [0, 1]
    assert (
        selected_equipment_id(candidates[0], EquipmentPart.HEAD) == fixed.equipment_id
    )


def test_response_scores_are_recomputed_from_public_skill_levels() -> None:
    first_id = "skill:first"
    second_id = "skill:second"
    head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:compound",
        skills=(contribution(first_id, 4), contribution(second_id, 2)),
    )
    preferences = (
        SkillPreference(first_id, 3),
        SkillPreference(second_id, 5),
    )

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
        ),
        payload=ranked_payload(
            preferences=[
                preference_payload(first_id, 3),
                preference_payload(second_id, 5),
            ],
            max_results=1,
        ),
    )

    candidate = response_candidates(response)[0]
    public_levels = {
        item["skill_id"]: item["level"] for item in candidate["skill_levels"]
    }
    assert candidate["preference_score"] == calculate_skill_preference_score(
        skill_levels=public_levels,
        preferences=preferences,
    )
    assert candidate["preference_score"] == 5
    json.dumps(response)


def test_unknown_preference_is_soft_and_scores_zero() -> None:
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")
    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(equipment=complete_equipment() + (second_head,)),
        payload=ranked_payload(
            preferences=[preference_payload("skill:unknown", 5)],
            max_results=2,
        ),
    )

    candidates = response_candidates(response)
    assert len(candidates) == 2
    assert [candidate["preference_score"] for candidate in candidates] == [0, 0]


def test_required_and_preferred_skill_may_overlap() -> None:
    skill_id = "skill:overlap"
    high = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:high",
        skills=(contribution(skill_id, 3),),
    )
    minimum = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:minimum",
        skills=(contribution(skill_id),),
    )
    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.HEAD: high})
            + (minimum,),
        ),
        payload=ranked_payload(
            requirements=[requirement_payload(skill_id)],
            preferences=[preference_payload(skill_id, 3)],
            max_results=2,
        ),
    )

    assert [
        candidate["preference_score"] for candidate in response_candidates(response)
    ] == [3, 1]


def test_partial_timeout_result_is_serialized_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    partial_candidate = BuildCandidate(
        equipment=(equipment_item(EquipmentPart.HEAD, "equipment:head:partial"),),
        placements=(),
        skill_levels=(("skill:preferred", 2),),
    )
    partial_result = CpSatBuildSearchResult(
        candidates=(partial_candidate,),
        exhausted=False,
        timed_out=True,
    )

    def fake_solver(**_kwargs: object) -> CpSatBuildSearchResult:
        return partial_result

    monkeypatch.setattr(
        search_service_module,
        "search_catalog_ranked_build_candidates_with_cp_sat",
        fake_solver,
    )

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(),
        payload=ranked_payload(
            preferences=[preference_payload("skill:preferred", 3)],
        ),
    )

    assert response["exhausted"] is False
    assert response["timed_out"] is True
    assert response_candidates(response)[0]["preference_score"] == 2


def test_objective_overflow_value_error_is_propagated() -> None:
    with pytest.raises(ValueError, match="preferences|objective"):
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=ranked_payload(
                preferences=[preference_payload("skill:huge", 10**100)],
                max_results=1,
            ),
        )


@pytest.mark.parametrize(
    ("invalid_payload", "expected_error"),
    [
        (None, TypeError),
        ({"requirements": [], "max_results": 1}, ValueError),
        (
            {
                "requirements": [],
                "preferences": [{"skill_id": "skill:test", "target_level": 0}],
                "max_results": 1,
            },
            ValueError,
        ),
    ],
)
def test_invalid_payload_errors_are_propagated(
    invalid_payload: object,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error):
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=invalid_payload,
        )


def test_solver_runtime_error_is_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    error = RuntimeError("solver failed")

    def fail_solver(**_kwargs: object) -> CpSatBuildSearchResult:
        raise error

    monkeypatch.setattr(
        search_service_module,
        "search_catalog_ranked_build_candidates_with_cp_sat",
        fail_solver,
    )

    with pytest.raises(RuntimeError) as exc_info:
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
            catalog=small_catalog(),
            payload=ranked_payload(),
        )

    assert exc_info.value is error


def test_catalog_and_payload_are_not_modified() -> None:
    skill_id = "skill:fixed"
    fixed_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:fixed",
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: fixed_head}),
    )
    payload_value = ranked_payload(
        requirements=[requirement_payload(skill_id)],
        preferences=[preference_payload(skill_id, 2)],
        max_results=1,
    )
    catalog_before = copy.deepcopy(catalog)
    payload_before = copy.deepcopy(payload_value)
    equipment_before = catalog.equipment

    search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=catalog,
        payload=payload_value,
    )

    assert catalog == catalog_before
    assert catalog.equipment is equipment_before
    assert payload_value == payload_before


def test_service_does_not_call_exhaustive_or_existing_non_ranked_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("ranked service must use only the ranked CP-SAT solver")

    monkeypatch.setattr(
        search_service_module,
        "search_catalog_build_candidates_from_payload",
        fail,
    )
    monkeypatch.setattr(
        search_service_module,
        "search_catalog_build_candidates_with_cp_sat_from_payload",
        fail,
    )
    monkeypatch.setattr(
        search_service_module,
        "search_catalog_build_candidates_with_cp_sat",
        fail,
    )
    monkeypatch.setattr(
        search_service_module,
        "search_limited_catalog_build_candidates_by_skill_requirements",
        fail,
    )

    response = search_catalog_ranked_build_candidates_with_cp_sat_from_payload(
        catalog=small_catalog(),
        payload=ranked_payload(
            preferences=[preference_payload("skill:unknown")],
            max_results=1,
        ),
    )

    assert len(response_candidates(response)) == 1


def test_service_function_has_no_fastapi_file_or_network_boundary_code() -> None:
    source = inspect.getsource(
        search_catalog_ranked_build_candidates_with_cp_sat_from_payload,
    ).lower()

    for forbidden in (
        "fastapi",
        "load_catalog",
        "pathlib",
        "read_text",
        "read_bytes",
        "open(",
        "requests",
        "httpx",
        "urllib",
    ):
        assert forbidden not in source
