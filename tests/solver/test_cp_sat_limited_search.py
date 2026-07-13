from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest
from ortools.sat.python import cp_model

import mhwilds_skill_sim.solver as solver_package
import mhwilds_skill_sim.solver.build as build_module
import mhwilds_skill_sim.solver.catalog_search as catalog_search_module
import mhwilds_skill_sim.solver.cp_sat_search as cp_sat_search_module
import mhwilds_skill_sim.solver.decoration as decoration_solver_module
import mhwilds_skill_sim.solver.equipment as equipment_solver_module
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
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
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.cp_sat_search import (
    CpSatBuildSearchResult,
    find_catalog_build_candidate_with_cp_sat,
    search_catalog_build_candidates_with_cp_sat,
)
from mhwilds_skill_sim.solver.requirements import (
    SkillRequirement,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.validation.build import BuildValidationResult, validate_build


REQUIRED_PARTS = tuple(EquipmentPart)


class CandidateTuple(tuple[BuildCandidate, ...]):
    pass


class RequirementTuple(tuple[SkillRequirement, ...]):
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
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
    weapon_kind: WeaponKind | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=slots,
        series_skill_id=series_skill_id,
        group_skill_id=group_skill_id,
        allows_series_skill_assignment=allows_series_skill_assignment,
        allows_group_skill_assignment=allows_group_skill_assignment,
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
    kind: DecorationKind,
    level: int = 1,
    skills: tuple[SkillContribution, ...],
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=slot(kind, level),
        skills=skills,
    )


def normal_skill(
    skill_id: str,
    *,
    maximum_level: int = 5,
    kind: SkillKind = SkillKind.ARMOR,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=tuple(
            SkillRankDefinition(level=level, required_pieces=None)
            for level in range(1, maximum_level + 1)
        ),
    )


def bonus_skill(
    skill_id: str,
    *,
    kind: SkillKind,
    thresholds: tuple[int, ...],
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=tuple(
            SkillRankDefinition(level=level, required_pieces=required_pieces)
            for level, required_pieces in enumerate(thresholds, start=1)
        ),
    )


def appraisal_group(
    group_id: str,
    *,
    skills: tuple[SkillContribution, ...],
) -> AppraisalCharmSkillGroupDefinition:
    return AppraisalCharmSkillGroupDefinition(group_id=group_id, skills=skills)


def appraisal_pattern(
    pattern_id: str,
    *,
    group_ids: tuple[str, ...],
) -> AppraisalCharmPatternDefinition:
    return AppraisalCharmPatternDefinition(
        pattern_id=pattern_id,
        rarity=8,
        skill_group_ids=group_ids,
        slots=(),
    )


def small_catalog(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    decorations: tuple[DecorationDefinition, ...] = (),
    skills: tuple[SkillDefinition, ...] = (),
    appraisal_groups: tuple[AppraisalCharmSkillGroupDefinition, ...] = (),
    appraisal_patterns: tuple[AppraisalCharmPatternDefinition, ...] = (),
) -> Catalog:
    return Catalog(
        schema_version=1,
        equipment=complete_equipment() if equipment is None else equipment,
        decorations=decorations,
        skills=skills,
        appraisal_charm_skill_groups=appraisal_groups,
        appraisal_charm_patterns=appraisal_patterns,
    )


def requirement(skill_id: str, level: int = 1) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=level)


def limited_search(
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...] = (),
    *,
    max_results: int = 10,
    weapon_kind: WeaponKind | None = None,
    timeout_seconds: float = 10.0,
) -> CpSatBuildSearchResult:
    return search_catalog_build_candidates_with_cp_sat(
        catalog=catalog,
        requirements=requirements,
        max_results=max_results,
        weapon_kind=weapon_kind,
        timeout_seconds=timeout_seconds,
    )


def result_candidate() -> BuildCandidate:
    return BuildCandidate(
        equipment=(equipment_item(EquipmentPart.WEAPON),),
        placements=(),
        skill_levels=(),
    )


def selected_item(
    candidate: BuildCandidate,
    part: EquipmentPart,
) -> EquipmentDefinition:
    return next(item for item in candidate.equipment if item.part is part)


def equipment_signature(
    candidate: BuildCandidate,
) -> tuple[EquipmentDefinition, ...]:
    return candidate.equipment


def requirement_generator() -> Iterator[SkillRequirement]:
    yield requirement("skill:test")


def test_result_type_keeps_empty_and_populated_values() -> None:
    candidate = result_candidate()

    empty = CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=False)
    populated = CpSatBuildSearchResult(
        candidates=(candidate,),
        exhausted=False,
        timed_out=True,
    )

    assert empty.candidates == ()
    assert empty.exhausted is True
    assert empty.timed_out is False
    assert populated.candidates == (candidate,)
    assert populated.exhausted is False
    assert populated.timed_out is True


def test_result_type_has_value_equality_and_hashing() -> None:
    result = CpSatBuildSearchResult(
        candidates=(result_candidate(),),
        exhausted=False,
        timed_out=False,
    )

    assert result == CpSatBuildSearchResult(
        candidates=(result_candidate(),),
        exhausted=False,
        timed_out=False,
    )
    assert result != CpSatBuildSearchResult(
        candidates=(),
        exhausted=True,
        timed_out=False,
    )
    assert {result, result} == {result}


def test_result_type_is_frozen() -> None:
    result = CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=False)

    with pytest.raises(FrozenInstanceError):
        result.exhausted = False  # type: ignore[misc]


@pytest.mark.parametrize(
    "candidates",
    [[result_candidate()], {result_candidate()}, iter((result_candidate(),)), None],
)
def test_result_type_requires_exact_candidates_tuple(candidates: object) -> None:
    with pytest.raises(TypeError, match="candidates"):
        CpSatBuildSearchResult(
            candidates=candidates,  # type: ignore[arg-type]
            exhausted=False,
            timed_out=False,
        )


def test_result_type_rejects_candidates_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="candidates"):
        CpSatBuildSearchResult(
            candidates=CandidateTuple((result_candidate(),)),
            exhausted=False,
            timed_out=False,
        )


@pytest.mark.parametrize("candidate", [None, "candidate", object()])
def test_result_type_rejects_invalid_candidate_items(candidate: object) -> None:
    with pytest.raises(TypeError, match="candidates"):
        CpSatBuildSearchResult(
            candidates=(candidate,),  # type: ignore[arg-type]
            exhausted=False,
            timed_out=False,
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("exhausted", 0),
        ("exhausted", 1),
        ("exhausted", "false"),
        ("exhausted", None),
        ("timed_out", 0),
        ("timed_out", 1),
        ("timed_out", "false"),
        ("timed_out", None),
    ],
)
def test_result_type_requires_exact_bool_flags(
    field_name: str,
    invalid_value: object,
) -> None:
    values: dict[str, object] = {
        "candidates": (),
        "exhausted": False,
        "timed_out": False,
    }
    values[field_name] = invalid_value

    with pytest.raises(TypeError, match=field_name):
        CpSatBuildSearchResult(**values)  # type: ignore[arg-type]


def test_result_type_rejects_simultaneous_exhaustion_and_timeout() -> None:
    with pytest.raises(ValueError, match="exhausted|timed_out"):
        CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=True)


def test_new_contract_is_directly_importable_but_not_package_exported() -> None:
    imported = importlib.import_module("mhwilds_skill_sim.solver.cp_sat_search")

    assert imported.CpSatBuildSearchResult is CpSatBuildSearchResult
    assert (
        imported.search_catalog_build_candidates_with_cp_sat
        is search_catalog_build_candidates_with_cp_sat
    )
    assert "CpSatBuildSearchResult" not in solver_package.__all__
    assert "search_catalog_build_candidates_with_cp_sat" not in solver_package.__all__
    assert not hasattr(solver_package, "CpSatBuildSearchResult")
    assert not hasattr(
        solver_package,
        "search_catalog_build_candidates_with_cp_sat",
    )


def test_limited_function_signature_is_keyword_only_with_required_defaults() -> None:
    parameters = inspect.signature(
        search_catalog_build_candidates_with_cp_sat,
    ).parameters

    assert tuple(parameters) == (
        "catalog",
        "requirements",
        "max_results",
        "weapon_kind",
        "timeout_seconds",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert parameters["catalog"].default is inspect.Parameter.empty
    assert parameters["requirements"].default is inspect.Parameter.empty
    assert parameters["max_results"].default is inspect.Parameter.empty
    assert parameters["weapon_kind"].default is None
    assert parameters["timeout_seconds"].default == 10.0


def test_limited_function_rejects_positional_arguments() -> None:
    with pytest.raises(TypeError):
        search_catalog_build_candidates_with_cp_sat(  # type: ignore[misc]
            small_catalog(),
            (),
            1,
            None,
            10.0,
        )


@pytest.mark.parametrize("max_results", [0, 1, 3])
def test_accepts_zero_and_positive_max_results(max_results: int) -> None:
    result = limited_search(small_catalog(), max_results=max_results)

    assert isinstance(result, CpSatBuildSearchResult)
    assert len(result.candidates) <= max_results


@pytest.mark.parametrize("max_results", [True, False, "1", 1.0, None])
def test_rejects_invalid_max_results_types(max_results: object) -> None:
    with pytest.raises(TypeError, match="max_results"):
        search_catalog_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            max_results=max_results,  # type: ignore[arg-type]
        )


def test_max_results_rejects_int_subclass() -> None:
    class IntSubclass(int):
        pass

    with pytest.raises(TypeError, match="max_results"):
        limited_search(
            small_catalog(),
            max_results=IntSubclass(1),
        )


def test_rejects_negative_max_results() -> None:
    with pytest.raises(ValueError, match="max_results"):
        limited_search(small_catalog(), max_results=-1)


@pytest.mark.parametrize("invalid_catalog", [None, object(), {}, ()])
def test_limited_search_rejects_invalid_catalog(invalid_catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        search_catalog_build_candidates_with_cp_sat(
            catalog=invalid_catalog,  # type: ignore[arg-type]
            requirements=(),
            max_results=1,
        )


def test_limited_search_accepts_catalog_subclass() -> None:
    class CatalogSubclass(Catalog):
        pass

    base = small_catalog()
    catalog = CatalogSubclass(
        schema_version=base.schema_version,
        equipment=base.equipment,
        decorations=base.decorations,
        skills=base.skills,
        appraisal_charm_skill_groups=base.appraisal_charm_skill_groups,
        appraisal_charm_patterns=base.appraisal_charm_patterns,
    )

    assert isinstance(limited_search(catalog, max_results=1), CpSatBuildSearchResult)


@pytest.mark.parametrize(
    "invalid_requirements",
    [
        [requirement("skill:test")],
        {requirement("skill:test")},
        requirement_generator(),
        None,
    ],
)
def test_limited_search_requires_exact_requirements_tuple(
    invalid_requirements: object,
) -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=invalid_requirements,  # type: ignore[arg-type]
            max_results=1,
        )


def test_limited_search_rejects_requirements_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="requirements"):
        limited_search(
            small_catalog(),
            RequirementTuple((requirement("skill:test"),)),
            max_results=1,
        )


@pytest.mark.parametrize("invalid_requirement", [None, "skill:test", object()])
def test_limited_search_rejects_invalid_requirement_items(
    invalid_requirement: object,
) -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(invalid_requirement,),  # type: ignore[arg-type]
            max_results=1,
        )


def test_limited_search_rejects_duplicate_requirement_skill_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        limited_search(
            small_catalog(),
            (requirement("skill:test"), requirement("skill:test", 2)),
            max_results=1,
        )


@pytest.mark.parametrize("invalid_weapon_kind", ["bow", 1, object()])
def test_limited_search_rejects_invalid_weapon_kind(
    invalid_weapon_kind: object,
) -> None:
    with pytest.raises(TypeError, match="weapon_kind"):
        search_catalog_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            max_results=1,
            weapon_kind=invalid_weapon_kind,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("timeout_seconds", [1, 1.0, 0.25])
def test_limited_search_accepts_positive_numeric_timeouts(
    timeout_seconds: int | float,
) -> None:
    assert isinstance(
        limited_search(
            small_catalog(),
            max_results=1,
            timeout_seconds=timeout_seconds,
        ),
        CpSatBuildSearchResult,
    )


@pytest.mark.parametrize(
    "invalid_timeout",
    [
        True,
        False,
        0,
        0.0,
        -1,
        -0.1,
        float("nan"),
        float("inf"),
        float("-inf"),
        "1",
        None,
    ],
)
def test_limited_search_rejects_invalid_timeouts(invalid_timeout: object) -> None:
    with pytest.raises((TypeError, ValueError), match="timeout_seconds"):
        search_catalog_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            max_results=1,
            timeout_seconds=invalid_timeout,  # type: ignore[arg-type]
        )


def test_limited_search_rejects_numeric_timeout_subclasses() -> None:
    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    for timeout_seconds in (IntSubclass(1), FloatSubclass(1.0)):
        with pytest.raises(TypeError, match="timeout_seconds"):
            limited_search(
                small_catalog(),
                max_results=1,
                timeout_seconds=timeout_seconds,
            )


def test_limited_search_does_not_mutate_inputs() -> None:
    catalog = small_catalog()
    requirements = (requirement("skill:missing"),)
    original_equipment = catalog.equipment
    original_decorations = catalog.decorations

    result = limited_search(catalog, requirements, max_results=2)

    assert result.candidates == ()
    assert catalog.equipment is original_equipment
    assert catalog.decorations is original_decorations
    assert requirements == (requirement("skill:missing"),)


@pytest.mark.parametrize("missing_part", REQUIRED_PARTS)
def test_missing_part_is_exhausted_without_invoking_solver(
    monkeypatch: pytest.MonkeyPatch,
    missing_part: EquipmentPart,
) -> None:
    def fail_solve(**_kwargs: object) -> object:
        raise AssertionError("CP-SAT must not be invoked for a missing part")

    monkeypatch.setattr(cp_sat_search_module, "_solve_model", fail_solve)
    equipment = tuple(
        item for item in complete_equipment() if item.part is not missing_part
    )

    assert limited_search(
        small_catalog(equipment=equipment),
        max_results=3,
    ) == CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=False)


def test_impossible_requirement_returns_exhausted_empty_result() -> None:
    result = limited_search(
        small_catalog(),
        (requirement("skill:impossible"),),
        max_results=3,
    )

    assert result == CpSatBuildSearchResult(
        candidates=(),
        exhausted=True,
        timed_out=False,
    )


def test_one_equipment_selection_is_returned_and_proven_exhausted() -> None:
    result = limited_search(small_catalog(), max_results=1)

    assert len(result.candidates) == 1
    assert result.exhausted is True
    assert result.timed_out is False
    assert result.candidates[0].equipment == complete_equipment()


def test_two_equipment_selections_are_returned_and_proven_exhausted() -> None:
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")
    catalog = small_catalog(equipment=complete_equipment() + (second_head,))

    result = limited_search(catalog, max_results=2)

    assert len(result.candidates) == 2
    assert result.exhausted is True
    assert result.timed_out is False
    assert len({equipment_signature(candidate) for candidate in result.candidates}) == 2


def test_more_solutions_than_limit_sets_non_exhausted_without_timeout() -> None:
    equipment = complete_equipment() + (
        equipment_item(EquipmentPart.HEAD, "equipment:head:second"),
        equipment_item(EquipmentPart.HEAD, "equipment:head:third"),
    )

    result = limited_search(small_catalog(equipment=equipment), max_results=2)

    assert len(result.candidates) == 2
    assert result.exhausted is False
    assert result.timed_out is False


def test_zero_limit_probes_existing_solution_without_returning_it() -> None:
    result = limited_search(small_catalog(), max_results=0)

    assert result == CpSatBuildSearchResult(
        candidates=(),
        exhausted=False,
        timed_out=False,
    )


def test_zero_limit_probes_infeasible_model_as_exhausted() -> None:
    result = limited_search(
        small_catalog(),
        (requirement("skill:impossible"),),
        max_results=0,
    )

    assert result == CpSatBuildSearchResult(
        candidates=(),
        exhausted=True,
        timed_out=False,
    )


def test_returned_equipment_is_distinct_and_in_part_declaration_order() -> None:
    equipment = tuple(reversed(complete_equipment())) + (
        equipment_item(EquipmentPart.HEAD, "equipment:head:second"),
        equipment_item(EquipmentPart.HEAD, "equipment:head:third"),
    )

    result = limited_search(small_catalog(equipment=equipment), max_results=3)

    assert len(result.candidates) == 3
    assert len({equipment_signature(candidate) for candidate in result.candidates}) == 3
    assert all(
        tuple(item.part for item in candidate.equipment) == REQUIRED_PARTS
        for candidate in result.candidates
    )


def test_repeated_identical_calls_return_equal_limited_results() -> None:
    equipment = complete_equipment() + (
        equipment_item(EquipmentPart.HEAD, "equipment:head:second"),
        equipment_item(EquipmentPart.CHEST, "equipment:chest:second"),
    )
    catalog = small_catalog(equipment=equipment)

    first = limited_search(catalog, max_results=3)
    second = limited_search(catalog, max_results=3)

    assert first == second


def test_existing_one_result_matches_first_limited_candidate() -> None:
    equipment = complete_equipment() + (
        equipment_item(EquipmentPart.HEAD, "equipment:head:second"),
    )
    catalog = small_catalog(equipment=equipment)

    one = find_catalog_build_candidate_with_cp_sat(catalog=catalog, requirements=())
    limited = limited_search(catalog, max_results=1)

    assert one is not None
    assert limited.candidates == (one,)


def test_decoration_minimizing_order_precedes_decorated_selection() -> None:
    skill_id = "skill:ordered"
    fixed_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:fixed-skill",
        skills=(contribution(skill_id),),
    )
    slotted_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:decoration",
        slots=(slot(DecorationKind.ARMOR),),
    )
    definition = decoration(
        "decoration:ordered",
        kind=DecorationKind.ARMOR,
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: fixed_head},
        )
        + (slotted_head,),
        decorations=(definition,),
    )

    result = limited_search(
        catalog,
        (requirement(skill_id),),
        max_results=2,
    )

    assert result.exhausted is True
    assert result.timed_out is False
    assert tuple(len(candidate.placements) for candidate in result.candidates) == (
        0,
        1,
    )
    assert (
        selected_item(
            result.candidates[0],
            EquipmentPart.HEAD,
        ).equipment_id
        == fixed_head.equipment_id
    )
    assert (
        selected_item(
            result.candidates[1],
            EquipmentPart.HEAD,
        ).equipment_id
        == slotted_head.equipment_id
    )


def test_decoration_counts_are_nondecreasing_across_results() -> None:
    skill_id = "skill:decoration-count"
    zero = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:zero",
        skills=(contribution(skill_id, 2),),
    )
    one = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:one",
        skills=(contribution(skill_id),),
        slots=(slot(DecorationKind.ARMOR),),
    )
    two = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:two",
        slots=(slot(DecorationKind.ARMOR), slot(DecorationKind.ARMOR)),
    )
    definition = decoration(
        "decoration:count",
        kind=DecorationKind.ARMOR,
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: zero})
        + (one, two),
        decorations=(definition,),
    )

    result = limited_search(
        catalog,
        (requirement(skill_id, 2),),
        max_results=3,
    )

    counts = tuple(len(candidate.placements) for candidate in result.candidates)
    assert counts == (0, 1, 2)
    assert counts == tuple(sorted(counts))


def test_equal_objective_tie_order_is_fixed_and_repeatable() -> None:
    first_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:first",
        skills=(contribution("skill:tie"),),
    )
    second_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:second",
        skills=(contribution("skill:tie"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: first_head},
        )
        + (second_head,),
    )

    first = limited_search(catalog, (requirement("skill:tie"),), max_results=2)
    second = limited_search(catalog, (requirement("skill:tie"),), max_results=2)

    assert first == second
    assert tuple(
        selected_item(candidate, EquipmentPart.HEAD).equipment_id
        for candidate in first.candidates
    ) == (second_head.equipment_id, first_head.equipment_id)


def test_one_selection_with_multiple_decoration_options_is_returned_once() -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(slot(DecorationKind.ARMOR),),
    )
    first = decoration(
        "decoration:first-option",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:option"),),
    )
    second = decoration(
        "decoration:second-option",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:option"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
        decorations=(first, second),
    )

    result = limited_search(
        catalog,
        (requirement("skill:option"),),
        max_results=5,
    )

    assert len(result.candidates) == 1
    assert len(result.candidates[0].placements) == 1
    assert result.exhausted is True
    assert result.timed_out is False


def test_placement_choice_and_output_order_remain_deterministic() -> None:
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        slots=(
            slot(DecorationKind.WEAPON, 3),
            slot(DecorationKind.WEAPON, 1),
        ),
    )
    low = decoration(
        "decoration:low",
        kind=DecorationKind.WEAPON,
        skills=(contribution("skill:low"),),
    )
    high = decoration(
        "decoration:high",
        kind=DecorationKind.WEAPON,
        level=3,
        skills=(contribution("skill:high"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.WEAPON: weapon},
        ),
        decorations=(low, high),
    )
    requirements = (requirement("skill:low"), requirement("skill:high"))

    first = limited_search(catalog, requirements, max_results=1)
    second = limited_search(catalog, requirements, max_results=1)

    assert first == second
    assert tuple(
        (placement.slot_index, placement.decoration_id)
        for placement in first.candidates[0].placements
    ) == ((0, high.decoration_id), (1, low.decoration_id))


def test_no_good_cut_excludes_only_exact_equipment_combination() -> None:
    first_head = equipment_item(EquipmentPart.HEAD, "equipment:head:first")
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")
    first_chest = equipment_item(EquipmentPart.CHEST, "equipment:chest:first")
    second_chest = equipment_item(EquipmentPart.CHEST, "equipment:chest:second")
    equipment = complete_equipment(
        replacements={
            EquipmentPart.HEAD: first_head,
            EquipmentPart.CHEST: first_chest,
        },
    ) + (second_head, second_chest)

    result = limited_search(small_catalog(equipment=equipment), max_results=4)

    selected_pairs = {
        (
            selected_item(candidate, EquipmentPart.HEAD).equipment_id,
            selected_item(candidate, EquipmentPart.CHEST).equipment_id,
        )
        for candidate in result.candidates
    }
    assert selected_pairs == {
        (first_head.equipment_id, first_chest.equipment_id),
        (first_head.equipment_id, second_chest.equipment_id),
        (second_head.equipment_id, first_chest.equipment_id),
        (second_head.equipment_id, second_chest.equipment_id),
    }
    assert result.exhausted is True
    assert result.timed_out is False


def test_extra_solution_probe_does_not_return_solution_beyond_limit() -> None:
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")

    result = limited_search(
        small_catalog(equipment=complete_equipment() + (second_head,)),
        max_results=1,
    )

    assert len(result.candidates) == 1
    assert result.exhausted is False
    assert result.timed_out is False


def test_infeasible_extra_probe_marks_limit_sized_result_exhausted() -> None:
    result = limited_search(small_catalog(), max_results=1)

    assert len(result.candidates) == 1
    assert result.exhausted is True
    assert result.timed_out is False


def test_weapon_kind_filtering_limits_results_to_matching_weapons() -> None:
    equipment = (
        equipment_item(
            EquipmentPart.WEAPON,
            "equipment:weapon:bow",
            weapon_kind=WeaponKind.BOW,
        ),
        equipment_item(
            EquipmentPart.WEAPON,
            "equipment:weapon:great-sword",
            weapon_kind=WeaponKind.GREAT_SWORD,
        ),
        *complete_equipment()[1:],
    )

    result = limited_search(
        small_catalog(equipment=equipment),
        max_results=2,
        weapon_kind=WeaponKind.BOW,
    )

    assert len(result.candidates) == 1
    assert (
        selected_item(
            result.candidates[0],
            EquipmentPart.WEAPON,
        ).weapon_kind
        is WeaponKind.BOW
    )
    assert result.exhausted is True


def test_artian_variants_with_shared_equipment_id_remain_distinct() -> None:
    first_series = "skill:series:first"
    second_series = "skill:series:second"
    artian = equipment_item(
        EquipmentPart.WEAPON,
        "equipment:weapon:artian",
        allows_series_skill_assignment=True,
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.WEAPON: artian},
        ),
        skills=(
            bonus_skill(first_series, kind=SkillKind.SERIES, thresholds=(1,)),
            bonus_skill(second_series, kind=SkillKind.SERIES, thresholds=(1,)),
        ),
    )

    result = limited_search(catalog, max_results=2)

    weapons = tuple(
        selected_item(candidate, EquipmentPart.WEAPON)
        for candidate in result.candidates
    )
    assert len(weapons) == 2
    assert {weapon.equipment_id for weapon in weapons} == {artian.equipment_id}
    assert {weapon.series_skill_id for weapon in weapons} == {
        first_series,
        second_series,
    }
    assert result.exhausted is True


def test_fixed_and_generated_appraisal_charms_are_both_usable() -> None:
    fixed_skill = "skill:fixed-charm"
    generated_skill = "skill:generated-charm"
    fixed_charm = equipment_item(
        EquipmentPart.CHARM,
        "equipment:charm:fixed",
        skills=(contribution(fixed_skill),),
    )
    group = appraisal_group(
        "appraisal-group:test",
        skills=(contribution(generated_skill),),
    )
    pattern = appraisal_pattern(
        "appraisal-pattern:test",
        group_ids=(group.group_id,),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.CHARM: fixed_charm},
        ),
        skills=(normal_skill(fixed_skill), normal_skill(generated_skill)),
        appraisal_groups=(group,),
        appraisal_patterns=(pattern,),
    )

    fixed_result = limited_search(
        catalog,
        (requirement(fixed_skill),),
        max_results=2,
    )
    generated_result = limited_search(
        catalog,
        (requirement(generated_skill),),
        max_results=2,
    )

    assert (
        selected_item(
            fixed_result.candidates[0],
            EquipmentPart.CHARM,
        )
        == fixed_charm
    )
    assert selected_item(
        generated_result.candidates[0],
        EquipmentPart.CHARM,
    ).equipment_id.startswith("generated:appraisal-charm:")
    assert fixed_result.exhausted is True
    assert generated_result.exhausted is True


def test_series_and_group_bonus_requirements_are_supported() -> None:
    series_id = "skill:series"
    group_id = "skill:group"
    replacements = {
        EquipmentPart.HEAD: equipment_item(
            EquipmentPart.HEAD,
            series_skill_id=series_id,
            group_skill_id=group_id,
        ),
        EquipmentPart.CHEST: equipment_item(
            EquipmentPart.CHEST,
            series_skill_id=series_id,
            group_skill_id=group_id,
        ),
        EquipmentPart.ARMS: equipment_item(
            EquipmentPart.ARMS,
            group_skill_id=group_id,
        ),
    }
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements),
        skills=(
            bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(2,)),
            bonus_skill(group_id, kind=SkillKind.GROUP, thresholds=(3,)),
        ),
    )
    requirements = (requirement(series_id), requirement(group_id))

    result = limited_search(catalog, requirements, max_results=1)

    assert len(result.candidates) == 1
    assert skill_levels_satisfy_requirements(
        skill_levels=dict(result.candidates[0].skill_levels),
        requirements=requirements,
    )
    assert result.exhausted is True


def test_compound_decoration_satisfies_all_requirements() -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(slot(DecorationKind.ARMOR),),
    )
    compound = decoration(
        "decoration:compound",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:first"), contribution("skill:second", 2)),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
        decorations=(compound,),
    )
    requirements = (
        requirement("skill:first"),
        requirement("skill:second", 2),
    )

    result = limited_search(catalog, requirements, max_results=1)

    assert len(result.candidates) == 1
    assert result.candidates[0].placements[0].decoration_id == compound.decoration_id
    assert skill_levels_satisfy_requirements(
        skill_levels=dict(result.candidates[0].skill_levels),
        requirements=requirements,
    )


def test_limited_search_does_not_call_exhaustive_search_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("limited CP-SAT search must not enumerate exhaustively")

    monkeypatch.setattr(build_module, "enumerate_build_candidates", fail)
    monkeypatch.setattr(equipment_solver_module, "enumerate_equipment_selections", fail)
    monkeypatch.setattr(
        decoration_solver_module,
        "enumerate_decoration_placement_combinations",
        fail,
    )
    monkeypatch.setattr(
        catalog_search_module,
        "search_catalog_build_candidates_by_skill_requirements",
        fail,
    )

    result = limited_search(small_catalog(), max_results=1)

    assert len(result.candidates) == 1


@pytest.mark.parametrize("max_results", [0, 1])
def test_unknown_before_candidate_returns_timed_out_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    max_results: int,
) -> None:
    monkeypatch.setattr(
        cp_sat_search_module,
        "_solve_model",
        lambda **_kwargs: (object(), cp_model.UNKNOWN),
    )

    result = limited_search(small_catalog(), max_results=max_results)

    assert result == CpSatBuildSearchResult(
        candidates=(),
        exhausted=False,
        timed_out=True,
    )


def test_unknown_after_candidate_preserves_valid_partial_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_solve = cp_sat_search_module._solve_model
    calls = 0

    def solve_then_unknown(**kwargs: object) -> tuple[object, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return original_solve(**kwargs)  # type: ignore[arg-type,return-value]
        return object(), cp_model.UNKNOWN

    monkeypatch.setattr(cp_sat_search_module, "_solve_model", solve_then_unknown)
    skill_id = "skill:partial"
    first_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:first",
        skills=(contribution(skill_id),),
    )
    second_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:second",
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: first_head},
        )
        + (second_head,),
    )
    requirements = (requirement(skill_id),)

    result = limited_search(catalog, requirements, max_results=2)

    assert len(result.candidates) == 1
    assert result.exhausted is False
    assert result.timed_out is True
    assert validate_build(
        equipment=result.candidates[0].equipment,
        decorations=catalog.decorations,
        placements=result.candidates[0].placements,
    ) == BuildValidationResult((), ())
    assert skill_levels_satisfy_requirements(
        skill_levels=dict(result.candidates[0].skill_levels),
        requirements=requirements,
    )


def test_budget_expiration_before_next_solve_preserves_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = iter((100.0, 100.0, 111.0))
    monkeypatch.setattr(cp_sat_search_module, "monotonic", lambda: next(times))
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")

    result = limited_search(
        small_catalog(equipment=complete_equipment() + (second_head,)),
        max_results=2,
        timeout_seconds=10.0,
    )

    assert len(result.candidates) == 1
    assert result.exhausted is False
    assert result.timed_out is True


def test_each_solve_reuses_model_and_receives_smaller_remaining_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_solve = cp_sat_search_module._solve_model
    times = iter((100.0, 101.0, 104.0))
    timeouts: list[float] = []
    model_ids: list[int] = []

    def recording_solve(**kwargs: object) -> tuple[object, object]:
        timeout_seconds = kwargs["timeout_seconds"]
        model = kwargs["model"]
        assert isinstance(timeout_seconds, float)
        timeouts.append(timeout_seconds)
        model_ids.append(id(model))
        return original_solve(**kwargs)  # type: ignore[arg-type,return-value]

    monkeypatch.setattr(cp_sat_search_module, "monotonic", lambda: next(times))
    monkeypatch.setattr(cp_sat_search_module, "_solve_model", recording_solve)
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")

    result = limited_search(
        small_catalog(equipment=complete_equipment() + (second_head,)),
        max_results=1,
        timeout_seconds=10.0,
    )

    assert result.exhausted is False
    assert result.timed_out is False
    assert timeouts == [9.0, 6.0]
    assert len(set(model_ids)) == 1


def test_preprocessing_time_is_charged_to_overall_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_prepare = cp_sat_search_module._prepare_candidates_by_part
    original_solve = cp_sat_search_module._solve_model
    now = [100.0]
    passed_timeouts: list[float] = []

    def elapsed_preprocessing(**kwargs: object) -> object:
        prepared = original_prepare(**kwargs)  # type: ignore[arg-type]
        now[0] = 106.0
        return prepared

    def recording_solve(**kwargs: object) -> tuple[object, object]:
        timeout_seconds = kwargs["timeout_seconds"]
        assert isinstance(timeout_seconds, float)
        passed_timeouts.append(timeout_seconds)
        return original_solve(**kwargs)  # type: ignore[arg-type,return-value]

    monkeypatch.setattr(cp_sat_search_module, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        cp_sat_search_module,
        "_prepare_candidates_by_part",
        elapsed_preprocessing,
    )
    monkeypatch.setattr(cp_sat_search_module, "_solve_model", recording_solve)

    result = limited_search(
        small_catalog(),
        max_results=0,
        timeout_seconds=10.0,
    )

    assert result.exhausted is False
    assert result.timed_out is False
    assert passed_timeouts == [4.0]


def test_preprocessing_can_exhaust_budget_before_first_solve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_prepare = cp_sat_search_module._prepare_candidates_by_part
    now = [100.0]

    def elapsed_preprocessing(**kwargs: object) -> object:
        prepared = original_prepare(**kwargs)  # type: ignore[arg-type]
        now[0] = 111.0
        return prepared

    def fail_solve(**_kwargs: object) -> object:
        raise AssertionError("CP-SAT must not start after the budget expires")

    monkeypatch.setattr(cp_sat_search_module, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        cp_sat_search_module,
        "_prepare_candidates_by_part",
        elapsed_preprocessing,
    )
    monkeypatch.setattr(cp_sat_search_module, "_solve_model", fail_solve)

    result = limited_search(
        small_catalog(),
        max_results=1,
        timeout_seconds=10.0,
    )

    assert result == CpSatBuildSearchResult(
        candidates=(),
        exhausted=False,
        timed_out=True,
    )


def test_feasible_candidate_is_returned_and_marks_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_solve = cp_sat_search_module._solve_model

    def feasible_solve(**kwargs: object) -> tuple[object, object]:
        solver, _status = original_solve(**kwargs)  # type: ignore[arg-type]
        return solver, cp_model.FEASIBLE

    monkeypatch.setattr(cp_sat_search_module, "_solve_model", feasible_solve)

    result = limited_search(small_catalog(), max_results=1)

    assert len(result.candidates) == 1
    assert result.exhausted is False
    assert result.timed_out is True


def test_feasible_extra_probe_is_not_returned_and_marks_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_solve = cp_sat_search_module._solve_model
    calls = 0

    def feasible_extra(**kwargs: object) -> tuple[object, object]:
        nonlocal calls
        calls += 1
        solver, status = original_solve(**kwargs)  # type: ignore[arg-type]
        if calls == 2:
            return solver, cp_model.FEASIBLE
        return solver, status

    monkeypatch.setattr(cp_sat_search_module, "_solve_model", feasible_extra)
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")

    result = limited_search(
        small_catalog(equipment=complete_equipment() + (second_head,)),
        max_results=1,
    )

    assert len(result.candidates) == 1
    assert result.exhausted is False
    assert result.timed_out is True


def test_model_invalid_status_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cp_sat_search_module,
        "_solve_model",
        lambda **_kwargs: (object(), cp_model.MODEL_INVALID),
    )

    with pytest.raises(RuntimeError, match="model"):
        limited_search(small_catalog(), max_results=1)


def test_unexpected_status_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cp_sat_search_module,
        "_solve_model",
        lambda **_kwargs: (object(), -999),
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        limited_search(small_catalog(), max_results=1)
