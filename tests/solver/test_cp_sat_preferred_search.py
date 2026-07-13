from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterator

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
    search_catalog_build_candidates_with_cp_sat,
    search_catalog_ranked_build_candidates_with_cp_sat,
)
from mhwilds_skill_sim.solver.preferences import (
    SkillPreference,
    calculate_skill_preference_score,
)
from mhwilds_skill_sim.solver.requirements import (
    SkillRequirement,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.validation.build import BuildValidationResult, validate_build


REQUIRED_PARTS = tuple(EquipmentPart)
DEFAULT_PREFERENCES = (SkillPreference("skill:preferred", 1),)


class PreferenceTuple(tuple[SkillPreference, ...]):
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
    additional_series_skill_ids: tuple[str, ...] = (),
    additional_group_skill_ids: tuple[str, ...] = (),
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
        additional_series_skill_ids=additional_series_skill_ids,
        additional_group_skill_ids=additional_group_skill_ids,
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


def preference(skill_id: str, level: int = 1) -> SkillPreference:
    return SkillPreference(skill_id=skill_id, target_level=level)


def ranked_search(
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...] = (),
    preferences: tuple[SkillPreference, ...] = DEFAULT_PREFERENCES,
    *,
    max_results: int = 10,
    weapon_kind: WeaponKind | None = None,
    timeout_seconds: float = 10.0,
) -> CpSatBuildSearchResult:
    return search_catalog_ranked_build_candidates_with_cp_sat(
        catalog=catalog,
        requirements=requirements,
        preferences=preferences,
        max_results=max_results,
        weapon_kind=weapon_kind,
        timeout_seconds=timeout_seconds,
    )


def selected_item(
    candidate: BuildCandidate,
    part: EquipmentPart,
) -> EquipmentDefinition:
    return next(item for item in candidate.equipment if item.part is part)


def candidate_score(
    candidate: BuildCandidate,
    preferences: tuple[SkillPreference, ...],
) -> int:
    return calculate_skill_preference_score(
        skill_levels=dict(candidate.skill_levels),
        preferences=preferences,
    )


def requirement_generator() -> Iterator[SkillRequirement]:
    yield requirement("skill:test")


def preference_generator() -> Iterator[SkillPreference]:
    yield preference("skill:test")


def test_ranked_contract_is_directly_importable_but_not_package_exported() -> None:
    imported = importlib.import_module("mhwilds_skill_sim.solver.cp_sat_search")

    assert (
        imported.search_catalog_ranked_build_candidates_with_cp_sat
        is search_catalog_ranked_build_candidates_with_cp_sat
    )
    assert (
        "search_catalog_ranked_build_candidates_with_cp_sat"
        not in solver_package.__all__
    )
    assert not hasattr(
        solver_package,
        "search_catalog_ranked_build_candidates_with_cp_sat",
    )


def test_ranked_function_signature_is_exactly_keyword_only() -> None:
    parameters = inspect.signature(
        search_catalog_ranked_build_candidates_with_cp_sat,
    ).parameters

    assert tuple(parameters) == (
        "catalog",
        "requirements",
        "preferences",
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
    assert parameters["preferences"].default is inspect.Parameter.empty
    assert parameters["max_results"].default is inspect.Parameter.empty
    assert parameters["weapon_kind"].default is None
    assert parameters["timeout_seconds"].default == 10.0


def test_ranked_function_rejects_positional_arguments() -> None:
    with pytest.raises(TypeError):
        search_catalog_ranked_build_candidates_with_cp_sat(  # type: ignore[misc]
            small_catalog(),
            (),
            DEFAULT_PREFERENCES,
            1,
            None,
            10.0,
        )


@pytest.mark.parametrize("max_results", [0, 1, 2])
def test_empty_preferences_exactly_match_existing_limited_search(
    max_results: int,
) -> None:
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")
    catalog = small_catalog(equipment=complete_equipment() + (second_head,))

    expected = search_catalog_build_candidates_with_cp_sat(
        catalog=catalog,
        requirements=(),
        max_results=max_results,
        weapon_kind=None,
        timeout_seconds=10.0,
    )
    actual = ranked_search(catalog, preferences=(), max_results=max_results)

    assert actual == expected


def test_empty_preferences_delegate_directly_to_existing_limited_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = small_catalog()
    requirements = (requirement("skill:required"),)
    sentinel = CpSatBuildSearchResult(candidates=(), exhausted=False, timed_out=True)
    calls: list[dict[str, object]] = []

    def fake_limited_search(**kwargs: object) -> CpSatBuildSearchResult:
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(
        cp_sat_search_module,
        "search_catalog_build_candidates_with_cp_sat",
        fake_limited_search,
    )

    result = ranked_search(
        catalog,
        requirements,
        (),
        max_results=3,
        weapon_kind=WeaponKind.BOW,
        timeout_seconds=2.5,
    )

    assert result is sentinel
    assert calls == [
        {
            "catalog": catalog,
            "requirements": requirements,
            "max_results": 3,
            "weapon_kind": WeaponKind.BOW,
            "timeout_seconds": 2.5,
        }
    ]


@pytest.mark.parametrize("invalid_catalog", [None, object(), {}, ()])
def test_ranked_search_rejects_invalid_catalog(invalid_catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=invalid_catalog,  # type: ignore[arg-type]
            requirements=(),
            preferences=DEFAULT_PREFERENCES,
            max_results=1,
        )


def test_ranked_search_accepts_catalog_subclass() -> None:
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

    assert isinstance(ranked_search(catalog, max_results=1), CpSatBuildSearchResult)


@pytest.mark.parametrize(
    "invalid_requirements",
    [
        [requirement("skill:test")],
        {requirement("skill:test")},
        requirement_generator(),
        None,
    ],
)
def test_ranked_search_preserves_exact_requirements_tuple_contract(
    invalid_requirements: object,
) -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=invalid_requirements,  # type: ignore[arg-type]
            preferences=DEFAULT_PREFERENCES,
            max_results=1,
        )


def test_ranked_search_rejects_requirements_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="requirements"):
        ranked_search(
            small_catalog(),
            RequirementTuple((requirement("skill:test"),)),
            max_results=1,
        )


@pytest.mark.parametrize("invalid_requirement", [None, "skill:test", object()])
def test_ranked_search_rejects_invalid_requirement_item(
    invalid_requirement: object,
) -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(invalid_requirement,),  # type: ignore[arg-type]
            preferences=DEFAULT_PREFERENCES,
            max_results=1,
        )


def test_ranked_search_rejects_duplicate_requirement_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        ranked_search(
            small_catalog(),
            (requirement("skill:test"), requirement("skill:test", 2)),
            max_results=1,
        )


@pytest.mark.parametrize(
    "invalid_preferences",
    [
        [preference("skill:test")],
        {preference("skill:test")},
        preference_generator(),
        None,
    ],
)
def test_ranked_search_requires_exact_preferences_tuple(
    invalid_preferences: object,
) -> None:
    with pytest.raises(TypeError, match="preferences"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            preferences=invalid_preferences,  # type: ignore[arg-type]
            max_results=1,
        )


def test_ranked_search_rejects_preference_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="preferences"):
        ranked_search(
            small_catalog(),
            preferences=PreferenceTuple((preference("skill:test"),)),
            max_results=1,
        )


@pytest.mark.parametrize("invalid_preference", [None, "skill:test", object()])
def test_ranked_search_rejects_invalid_preference_item(
    invalid_preference: object,
) -> None:
    with pytest.raises(TypeError, match="preferences"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            preferences=(invalid_preference,),  # type: ignore[arg-type]
            max_results=1,
        )


def test_ranked_search_rejects_duplicate_preference_ids() -> None:
    with pytest.raises(ValueError, match="preferences"):
        ranked_search(
            small_catalog(),
            preferences=(
                preference("skill:test"),
                preference("skill:test", 2),
            ),
            max_results=1,
        )


@pytest.mark.parametrize("max_results", [0, 1, 3])
def test_ranked_search_accepts_zero_and_positive_max_results(
    max_results: int,
) -> None:
    result = ranked_search(small_catalog(), max_results=max_results)

    assert isinstance(result, CpSatBuildSearchResult)
    assert len(result.candidates) <= max_results


@pytest.mark.parametrize("max_results", [True, False, "1", 1.0, None])
def test_ranked_search_rejects_invalid_max_results_types(
    max_results: object,
) -> None:
    with pytest.raises(TypeError, match="max_results"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            preferences=DEFAULT_PREFERENCES,
            max_results=max_results,  # type: ignore[arg-type]
        )


def test_ranked_search_rejects_int_subclass_and_negative_max_results() -> None:
    class IntSubclass(int):
        pass

    for max_results in (IntSubclass(1), -1):
        with pytest.raises((TypeError, ValueError), match="max_results"):
            ranked_search(
                small_catalog(),
                max_results=max_results,  # type: ignore[arg-type]
            )


@pytest.mark.parametrize("invalid_weapon_kind", ["bow", 1, object()])
def test_ranked_search_preserves_weapon_kind_contract(
    invalid_weapon_kind: object,
) -> None:
    with pytest.raises(TypeError, match="weapon_kind"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            preferences=DEFAULT_PREFERENCES,
            max_results=1,
            weapon_kind=invalid_weapon_kind,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("timeout_seconds", [1, 1.0, 0.25])
def test_ranked_search_accepts_positive_numeric_timeouts(
    timeout_seconds: int | float,
) -> None:
    assert isinstance(
        ranked_search(
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
def test_ranked_search_rejects_invalid_timeouts(invalid_timeout: object) -> None:
    with pytest.raises((TypeError, ValueError), match="timeout_seconds"):
        search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            preferences=DEFAULT_PREFERENCES,
            max_results=1,
            timeout_seconds=invalid_timeout,  # type: ignore[arg-type]
        )


def test_ranked_search_rejects_numeric_timeout_subclasses() -> None:
    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    for timeout_seconds in (IntSubclass(1), FloatSubclass(1.0)):
        with pytest.raises(TypeError, match="timeout_seconds"):
            ranked_search(
                small_catalog(),
                max_results=1,
                timeout_seconds=timeout_seconds,
            )


def test_required_and_preferred_overlap_is_accepted() -> None:
    skill_id = "skill:overlap"
    head = equipment_item(
        EquipmentPart.HEAD,
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
    )

    result = ranked_search(
        catalog,
        (requirement(skill_id),),
        (preference(skill_id, 2),),
        max_results=1,
    )

    assert len(result.candidates) == 1
    assert candidate_score(result.candidates[0], (preference(skill_id, 2),)) == 1


def test_ranked_search_rejects_objective_overflow_before_solving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_solve(**_kwargs: object) -> object:
        raise AssertionError("overflow must be rejected before CP-SAT solve")

    monkeypatch.setattr(cp_sat_search_module, "_solve_model", fail_solve)

    with pytest.raises(ValueError, match="preferences|objective"):
        ranked_search(
            small_catalog(),
            preferences=(preference("skill:huge", 10**100),),
            max_results=1,
        )


def test_ranked_search_does_not_mutate_inputs() -> None:
    catalog = small_catalog()
    requirements = (requirement("skill:missing"),)
    preferences = (preference("skill:preferred", 3),)
    original_equipment = catalog.equipment
    original_decorations = catalog.decorations
    original_skills = catalog.skills

    result = ranked_search(
        catalog,
        requirements,
        preferences,
        max_results=2,
    )

    assert result.candidates == ()
    assert catalog.equipment is original_equipment
    assert catalog.decorations is original_decorations
    assert catalog.skills is original_skills
    assert requirements == (requirement("skill:missing"),)
    assert preferences == (preference("skill:preferred", 3),)


@pytest.mark.parametrize("part", [EquipmentPart.HEAD, EquipmentPart.WEAPON])
def test_fixed_armor_and_weapon_skills_rank_higher_score_first(
    part: EquipmentPart,
) -> None:
    skill_id = f"skill:{part.value}:preferred"
    high = equipment_item(
        part,
        f"equipment:{part.value}:high",
        skills=(contribution(skill_id, 3),),
    )
    low = equipment_item(
        part,
        f"equipment:{part.value}:low",
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={part: high}) + (low,),
    )
    preferences = (preference(skill_id, 3),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        3,
        1,
    )
    assert selected_item(result.candidates[0], part).equipment_id == high.equipment_id


def test_decoration_score_outweighs_any_decoration_count_difference() -> None:
    skill_id = "skill:decoration-priority"
    fixed_low = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:fixed-low",
        skills=(contribution(skill_id),),
    )
    slotted_high = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:slotted-high",
        slots=(slot(DecorationKind.ARMOR),),
    )
    high_decoration = decoration(
        "decoration:preferred-high",
        kind=DecorationKind.ARMOR,
        skills=(contribution(skill_id, 2),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: fixed_low},
        )
        + (slotted_high,),
        decorations=(high_decoration,),
    )
    preferences = (preference(skill_id, 2),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        2,
        1,
    )
    assert tuple(len(candidate.placements) for candidate in result.candidates) == (1, 0)
    assert (
        selected_item(result.candidates[0], EquipmentPart.HEAD).equipment_id
        == slotted_high.equipment_id
    )


def test_compound_decoration_contributes_every_preferred_skill() -> None:
    first_skill = "skill:compound:first"
    second_skill = "skill:compound:second"
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(slot(DecorationKind.ARMOR),),
    )
    compound = decoration(
        "decoration:compound-preferred",
        kind=DecorationKind.ARMOR,
        skills=(contribution(first_skill), contribution(second_skill, 2)),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
        decorations=(compound,),
    )
    preferences = (preference(first_skill), preference(second_skill, 2))

    result = ranked_search(catalog, preferences=preferences, max_results=1)

    assert len(result.candidates) == 1
    assert candidate_score(result.candidates[0], preferences) == 3
    assert dict(result.candidates[0].skill_levels) == {
        first_skill: 1,
        second_skill: 2,
    }
    assert result.candidates[0].placements[0].decoration_id == compound.decoration_id


def test_target_cap_makes_decoration_count_the_tie_break() -> None:
    skill_id = "skill:capped"
    fixed_over_cap = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:fixed-over-cap",
        skills=(contribution(skill_id, 4),),
    )
    decorated_over_cap = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:decorated-over-cap",
        slots=(slot(DecorationKind.ARMOR),),
    )
    definition = decoration(
        "decoration:over-cap",
        kind=DecorationKind.ARMOR,
        skills=(contribution(skill_id, 5),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: fixed_over_cap},
        )
        + (decorated_over_cap,),
        decorations=(definition,),
    )
    preferences = (preference(skill_id, 2),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        2,
        2,
    )
    assert tuple(len(candidate.placements) for candidate in result.candidates) == (0, 1)
    assert (
        selected_item(result.candidates[0], EquipmentPart.HEAD).equipment_id
        == fixed_over_cap.equipment_id
    )
    assert dict(result.candidates[1].skill_levels)[skill_id] == 5


def test_multiple_preferences_are_summed_without_tuple_priority() -> None:
    first_skill = "skill:tuple:first"
    second_skill = "skill:tuple:second"
    first_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:first-preference",
        skills=(contribution(first_skill, 2),),
    )
    second_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:second-preference",
        skills=(contribution(second_skill, 3),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: first_head},
        )
        + (second_head,),
    )
    preferences = (preference(first_skill, 2), preference(second_skill, 3))
    reversed_preferences = tuple(reversed(preferences))

    first_result = ranked_search(catalog, preferences=preferences, max_results=2)
    reversed_result = ranked_search(
        catalog,
        preferences=reversed_preferences,
        max_results=2,
    )

    assert tuple(
        candidate_score(candidate, preferences) for candidate in first_result.candidates
    ) == (
        3,
        2,
    )
    assert (
        selected_item(first_result.candidates[0], EquipmentPart.HEAD).equipment_id
        == second_head.equipment_id
    )
    assert tuple(
        candidate.equipment for candidate in reversed_result.candidates
    ) == tuple(candidate.equipment for candidate in first_result.candidates)


def test_unknown_preference_scores_zero_without_becoming_hard_constraint() -> None:
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")
    catalog = small_catalog(equipment=complete_equipment() + (second_head,))
    preferences = (preference("skill:unknown", 5),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert len(result.candidates) == 2
    assert all(
        candidate_score(candidate, preferences) == 0 for candidate in result.candidates
    )
    assert result.exhausted is True
    assert result.timed_out is False


def test_required_preferred_overlap_ranks_above_required_minimum() -> None:
    skill_id = "skill:required-preferred"
    high = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:overlap-high",
        skills=(contribution(skill_id, 3),),
    )
    minimum = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:overlap-minimum",
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: high})
        + (minimum,),
    )
    requirements = (requirement(skill_id),)
    preferences = (preference(skill_id, 3),)

    result = ranked_search(
        catalog,
        requirements,
        preferences,
        max_results=2,
    )

    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        3,
        1,
    )
    assert all(
        skill_levels_satisfy_requirements(
            skill_levels=dict(candidate.skill_levels),
            requirements=requirements,
        )
        for candidate in result.candidates
    )


def test_high_preference_candidate_that_breaks_hard_requirement_is_excluded() -> None:
    preferred_id = "skill:soft"
    required_id = "skill:hard"
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
    requirements = (requirement(required_id),)
    preferences = (preference(preferred_id, 5),)

    result = ranked_search(
        catalog,
        requirements,
        preferences,
        max_results=2,
    )

    assert len(result.candidates) == 1
    assert (
        selected_item(result.candidates[0], EquipmentPart.HEAD).equipment_id
        == valid_lower.equipment_id
    )
    assert candidate_score(result.candidates[0], preferences) == 1
    assert result.exhausted is True


@pytest.mark.parametrize(
    ("kind", "membership_field", "required_pieces", "common_parts"),
    [
        (SkillKind.SERIES, "series_skill_id", 2, (EquipmentPart.CHEST,)),
        (
            SkillKind.SERIES,
            "additional_series_skill_ids",
            2,
            (EquipmentPart.CHEST,),
        ),
        (
            SkillKind.GROUP,
            "group_skill_id",
            3,
            (EquipmentPart.CHEST, EquipmentPart.ARMS),
        ),
        (
            SkillKind.GROUP,
            "additional_group_skill_ids",
            3,
            (EquipmentPart.CHEST, EquipmentPart.ARMS),
        ),
    ],
)
def test_primary_and_additional_series_and_group_memberships_are_scored(
    kind: SkillKind,
    membership_field: str,
    required_pieces: int,
    common_parts: tuple[EquipmentPart, ...],
) -> None:
    skill_id = f"skill:{kind.value}:{membership_field}"
    membership_value: object = (
        (skill_id,) if membership_field.startswith("additional_") else skill_id
    )
    membership = {membership_field: membership_value}
    high_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:bonus-high",
        **membership,  # type: ignore[arg-type]
    )
    low_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:bonus-low",
    )
    replacements = {EquipmentPart.HEAD: high_head}
    replacements.update(
        {
            part: equipment_item(
                part,
                **membership,  # type: ignore[arg-type]
            )
            for part in common_parts
        }
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements) + (low_head,),
        skills=(bonus_skill(skill_id, kind=kind, thresholds=(required_pieces,)),),
    )
    preferences = (preference(skill_id),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        1,
        0,
    )
    assert dict(result.candidates[0].skill_levels)[skill_id] == 1
    assert skill_id not in dict(result.candidates[1].skill_levels)
    assert (
        selected_item(result.candidates[0], EquipmentPart.HEAD).equipment_id
        == high_head.equipment_id
    )


@pytest.mark.parametrize("kind", [SkillKind.SERIES, SkillKind.GROUP])
def test_bonus_preference_uses_activated_rank_not_piece_marker_count(
    kind: SkillKind,
) -> None:
    skill_id = f"skill:{kind.value}:ranked-level"
    membership_field = (
        "series_skill_id" if kind is SkillKind.SERIES else "group_skill_id"
    )
    membership = {membership_field: skill_id}
    high_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:rank-two",
        **membership,  # type: ignore[arg-type]
    )
    low_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:rank-one",
    )
    replacements = {
        EquipmentPart.HEAD: high_head,
        EquipmentPart.CHEST: equipment_item(
            EquipmentPart.CHEST,
            **membership,  # type: ignore[arg-type]
        ),
        EquipmentPart.ARMS: equipment_item(
            EquipmentPart.ARMS,
            **membership,  # type: ignore[arg-type]
        ),
        EquipmentPart.WAIST: equipment_item(
            EquipmentPart.WAIST,
            **membership,  # type: ignore[arg-type]
        ),
    }
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements) + (low_head,),
        skills=(bonus_skill(skill_id, kind=kind, thresholds=(2, 4)),),
    )
    preferences = (preference(skill_id, 5),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert tuple(
        dict(candidate.skill_levels)[skill_id] for candidate in result.candidates
    ) == (
        2,
        1,
    )
    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        2,
        1,
    )


def test_artian_assignment_is_scored_and_shared_equipment_id_variants_are_distinct() -> (
    None
):
    first_series = "skill:artian:first"
    preferred_series = "skill:artian:preferred"
    artian = equipment_item(
        EquipmentPart.WEAPON,
        "equipment:weapon:artian-shared",
        allows_series_skill_assignment=True,
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.WEAPON: artian}),
        skills=(
            bonus_skill(first_series, kind=SkillKind.SERIES, thresholds=(1,)),
            bonus_skill(preferred_series, kind=SkillKind.SERIES, thresholds=(1,)),
        ),
    )
    preferences = (preference(preferred_series),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    weapons = tuple(
        selected_item(candidate, EquipmentPart.WEAPON)
        for candidate in result.candidates
    )
    assert len(weapons) == 2
    assert {weapon.equipment_id for weapon in weapons} == {artian.equipment_id}
    assert tuple(weapon.series_skill_id for weapon in weapons) == (
        preferred_series,
        first_series,
    )
    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        1,
        0,
    )
    assert result.exhausted is True


def test_generated_appraisal_charm_preference_ranks_before_fixed_charm() -> None:
    skill_id = "skill:generated-charm-preferred"
    fixed_charm = equipment_item(
        EquipmentPart.CHARM,
        "equipment:charm:fixed-empty",
    )
    group = appraisal_group(
        "appraisal-group:preferred",
        skills=(contribution(skill_id, 2),),
    )
    pattern = appraisal_pattern(
        "appraisal-pattern:preferred",
        group_ids=(group.group_id,),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.CHARM: fixed_charm},
        ),
        skills=(normal_skill(skill_id),),
        appraisal_groups=(group,),
        appraisal_patterns=(pattern,),
    )
    preferences = (preference(skill_id, 2),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert selected_item(
        result.candidates[0],
        EquipmentPart.CHARM,
    ).equipment_id.startswith("generated:appraisal-charm:")
    assert candidate_score(result.candidates[0], preferences) == 2
    assert selected_item(result.candidates[1], EquipmentPart.CHARM) is fixed_charm


def test_fixed_charm_skill_is_included_in_preference_score() -> None:
    skill_id = "skill:fixed-charm-preferred"
    preferred_charm = equipment_item(
        EquipmentPart.CHARM,
        "equipment:charm:preferred",
        skills=(contribution(skill_id, 2),),
    )
    plain_charm = equipment_item(
        EquipmentPart.CHARM,
        "equipment:charm:plain",
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.CHARM: preferred_charm},
        )
        + (plain_charm,),
    )
    preferences = (preference(skill_id, 2),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert selected_item(result.candidates[0], EquipmentPart.CHARM) is preferred_charm
    assert tuple(
        candidate_score(candidate, preferences) for candidate in result.candidates
    ) == (
        2,
        0,
    )


def test_score_order_and_decoration_tie_break_hold_across_all_candidates() -> None:
    skill_id = "skill:global-order"
    score_two_zero = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:score-two-zero",
        skills=(contribution(skill_id, 2),),
    )
    score_two_one = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:score-two-one",
        skills=(contribution(skill_id),),
        slots=(slot(DecorationKind.ARMOR),),
    )
    score_one_zero = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:score-one-zero",
        skills=(contribution(skill_id),),
    )
    score_one_one = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:score-one-one",
        slots=(slot(DecorationKind.ARMOR),),
    )
    definition = decoration(
        "decoration:global-order",
        kind=DecorationKind.ARMOR,
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: score_two_zero},
        )
        + (score_two_one, score_one_zero, score_one_one),
        decorations=(definition,),
    )
    preferences = (preference(skill_id, 2),)

    first = ranked_search(catalog, preferences=preferences, max_results=4)
    second = ranked_search(catalog, preferences=preferences, max_results=4)

    scores = tuple(
        candidate_score(candidate, preferences) for candidate in first.candidates
    )
    decoration_counts = tuple(
        len(candidate.placements) for candidate in first.candidates
    )
    assert scores == (2, 2, 1, 1)
    assert decoration_counts == (0, 1, 0, 1)
    assert scores == tuple(sorted(scores, reverse=True))
    assert all(
        left_score != right_score or left_count <= right_count
        for left_score, right_score, left_count, right_count in zip(
            scores,
            scores[1:],
            decoration_counts,
            decoration_counts[1:],
        )
    )
    assert second == first
    assert first.exhausted is True
    assert first.timed_out is False


def test_weapon_kind_filter_is_applied_before_preference_ranking() -> None:
    skill_id = "skill:weapon-filter"
    bow = equipment_item(
        EquipmentPart.WEAPON,
        "equipment:weapon:bow",
        skills=(contribution(skill_id),),
        weapon_kind=WeaponKind.BOW,
    )
    great_sword = equipment_item(
        EquipmentPart.WEAPON,
        "equipment:weapon:great-sword",
        skills=(contribution(skill_id, 5),),
        weapon_kind=WeaponKind.GREAT_SWORD,
    )
    catalog = small_catalog(
        equipment=(bow, great_sword, *complete_equipment()[1:]),
    )

    result = ranked_search(
        catalog,
        preferences=(preference(skill_id, 5),),
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


def test_every_returned_candidate_is_valid_and_satisfies_hard_requirements() -> None:
    preferred_id = "skill:validated-preferred"
    required_id = "skill:validated-required"
    required_chest = equipment_item(
        EquipmentPart.CHEST,
        skills=(contribution(required_id),),
    )
    fixed_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:validated-fixed",
        skills=(contribution(preferred_id, 2),),
    )
    slotted_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:validated-slotted",
        slots=(slot(DecorationKind.ARMOR),),
    )
    definition = decoration(
        "decoration:validated",
        kind=DecorationKind.ARMOR,
        skills=(contribution(preferred_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={
                EquipmentPart.HEAD: fixed_head,
                EquipmentPart.CHEST: required_chest,
            },
        )
        + (slotted_head,),
        decorations=(definition,),
    )
    requirements = (requirement(required_id),)

    result = ranked_search(
        catalog,
        requirements,
        (preference(preferred_id, 2),),
        max_results=2,
    )

    assert len(result.candidates) == 2
    for candidate in result.candidates:
        assert validate_build(
            equipment=candidate.equipment,
            decorations=catalog.decorations,
            placements=candidate.placements,
        ) == BuildValidationResult((), ())
        assert skill_levels_satisfy_requirements(
            skill_levels=dict(candidate.skill_levels),
            requirements=requirements,
        )


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

    assert ranked_search(
        small_catalog(equipment=equipment),
        max_results=3,
    ) == CpSatBuildSearchResult(candidates=(), exhausted=True, timed_out=False)


def test_impossible_hard_requirement_returns_exhausted_empty_result() -> None:
    result = ranked_search(
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
    result = ranked_search(small_catalog(), max_results=1)

    assert len(result.candidates) == 1
    assert result.candidates[0].equipment == complete_equipment()
    assert result.exhausted is True
    assert result.timed_out is False


def test_fewer_solutions_than_limit_are_all_returned_and_exhausted() -> None:
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")

    result = ranked_search(
        small_catalog(equipment=complete_equipment() + (second_head,)),
        max_results=3,
    )

    assert len(result.candidates) == 2
    assert len({candidate.equipment for candidate in result.candidates}) == 2
    assert result.exhausted is True
    assert result.timed_out is False


def test_limit_reached_with_additional_solution_is_not_exhausted() -> None:
    second_head = equipment_item(EquipmentPart.HEAD, "equipment:head:second")

    result = ranked_search(
        small_catalog(equipment=complete_equipment() + (second_head,)),
        max_results=1,
    )

    assert len(result.candidates) == 1
    assert result.exhausted is False
    assert result.timed_out is False


def test_zero_limit_probes_existing_solution_without_returning_it() -> None:
    result = ranked_search(small_catalog(), max_results=0)

    assert result == CpSatBuildSearchResult(
        candidates=(),
        exhausted=False,
        timed_out=False,
    )


def test_zero_limit_probes_infeasible_model_as_exhausted() -> None:
    result = ranked_search(
        small_catalog(),
        (requirement("skill:impossible"),),
        max_results=0,
    )

    assert result == CpSatBuildSearchResult(
        candidates=(),
        exhausted=True,
        timed_out=False,
    )


def test_no_good_cut_excludes_only_exact_equipment_selection() -> None:
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

    result = ranked_search(small_catalog(equipment=equipment), max_results=4)

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


def test_decoration_variants_do_not_duplicate_same_equipment_selection() -> None:
    skill_id = "skill:decoration-variant"
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(slot(DecorationKind.ARMOR),),
    )
    first = decoration(
        "decoration:variant:first",
        kind=DecorationKind.ARMOR,
        skills=(contribution(skill_id),),
    )
    second = decoration(
        "decoration:variant:second",
        kind=DecorationKind.ARMOR,
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
        decorations=(first, second),
    )

    result = ranked_search(
        catalog,
        preferences=(preference(skill_id),),
        max_results=5,
    )

    assert len(result.candidates) == 1
    assert len(result.candidates[0].placements) == 1
    assert result.candidates[0].placements[0].decoration_id in {
        first.decoration_id,
        second.decoration_id,
    }
    assert result.exhausted is True


def test_primary_and_additional_membership_equipment_remain_distinct() -> None:
    skill_id = "skill:cross-membership-distinct"
    primary_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:primary-series",
        series_skill_id=skill_id,
    )
    additional_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:additional-series",
        additional_series_skill_ids=(skill_id,),
    )
    chest = equipment_item(
        EquipmentPart.CHEST,
        additional_series_skill_ids=(skill_id,),
    )
    catalog = small_catalog(
        equipment=(
            complete_equipment()[0],
            primary_head,
            additional_head,
            chest,
            *complete_equipment()[3:],
        ),
        skills=(bonus_skill(skill_id, kind=SkillKind.SERIES, thresholds=(2,)),),
    )
    preferences = (preference(skill_id),)

    result = ranked_search(catalog, preferences=preferences, max_results=2)

    assert {
        selected_item(candidate, EquipmentPart.HEAD).equipment_id
        for candidate in result.candidates
    } == {primary_head.equipment_id, additional_head.equipment_id}
    assert all(
        candidate_score(candidate, preferences) == 1 for candidate in result.candidates
    )
    assert result.exhausted is True


def test_ranked_search_does_not_call_exhaustive_search_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("ranked CP-SAT search must not enumerate exhaustively")

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

    result = ranked_search(small_catalog(), max_results=1)

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

    result = ranked_search(small_catalog(), max_results=max_results)

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
        "equipment:head:partial:first",
        skills=(contribution(skill_id, 2),),
    )
    second_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:partial:second",
        skills=(contribution(skill_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={EquipmentPart.HEAD: first_head},
        )
        + (second_head,),
    )
    requirements = (requirement(skill_id),)
    preferences = (preference(skill_id, 2),)

    result = ranked_search(
        catalog,
        requirements,
        preferences,
        max_results=2,
    )

    assert len(result.candidates) == 1
    assert result.exhausted is False
    assert result.timed_out is True
    assert candidate_score(result.candidates[0], preferences) == 2
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

    result = ranked_search(
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

    result = ranked_search(
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

    result = ranked_search(
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

    result = ranked_search(
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

    result = ranked_search(small_catalog(), max_results=1)

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

    result = ranked_search(
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
        ranked_search(small_catalog(), max_results=1)


def test_unexpected_status_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cp_sat_search_module,
        "_solve_model",
        lambda **_kwargs: (object(), -999),
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        ranked_search(small_catalog(), max_results=1)
