from __future__ import annotations

import importlib
import inspect
import tomllib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

import mhwilds_skill_sim.solver as solver_package
import mhwilds_skill_sim.solver.build as build_module
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
    find_catalog_build_candidate_with_cp_sat,
)
from mhwilds_skill_sim.solver.requirements import (
    SkillRequirement,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.validation.build import BuildValidationResult, validate_build


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PARTS = tuple(EquipmentPart)
EXPECTED_SOLVER_ALL = [
    "BuildCandidate",
    "BuildCandidateSearchResult",
    "SkillRequirement",
    "enumerate_build_candidates",
    "enumerate_decoration_placement_combinations",
    "enumerate_equipment_selections",
    "expand_equipment_bonus_skill_variants",
    "filter_equipment_candidates_by_weapon_kind",
    "filter_build_candidates_by_skill_requirements",
    "generate_appraisal_charm_equipment_candidates",
    "search_catalog_build_candidates_by_skill_requirements",
    "search_build_candidates_by_skill_requirements",
    "search_limited_catalog_build_candidates_by_skill_requirements",
    "skill_levels_satisfy_requirements",
]


def contribution(skill_id: str, level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id=skill_id, level=level)


def slot(kind: DecorationKind, level: int = 1) -> DecorationSlot:
    return DecorationSlot(kind=kind, level=level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return slot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return slot(DecorationKind.ARMOR, level)


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
    slots: tuple[DecorationSlot, ...] = (),
) -> AppraisalCharmPatternDefinition:
    return AppraisalCharmPatternDefinition(
        pattern_id=pattern_id,
        rarity=8,
        skill_group_ids=group_ids,
        slots=slots,
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


def solve(
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...] = (),
    *,
    weapon_kind: WeaponKind | None = None,
    timeout_seconds: float = 10.0,
) -> BuildCandidate | None:
    return find_catalog_build_candidate_with_cp_sat(
        catalog=catalog,
        requirements=requirements,
        weapon_kind=weapon_kind,
        timeout_seconds=timeout_seconds,
    )


def selected_item(
    candidate: BuildCandidate, part: EquipmentPart
) -> EquipmentDefinition:
    return next(item for item in candidate.equipment if item.part is part)


def requirement_generator() -> Iterator[SkillRequirement]:
    yield requirement("skill:test")


def test_runtime_dependencies_add_only_exact_ortools_requirement() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]

    assert project["dependencies"] == [
        "fastapi>=0.115,<1",
        "ortools>=9.15,<10",
        "uvicorn>=0.51,<1",
    ]


def test_direct_cp_sat_module_import_exposes_function() -> None:
    imported = importlib.import_module("mhwilds_skill_sim.solver.cp_sat_search")

    assert (
        imported.find_catalog_build_candidate_with_cp_sat
        is find_catalog_build_candidate_with_cp_sat
    )


def test_cp_sat_function_is_intentionally_absent_from_solver_exports() -> None:
    assert solver_package.__all__ == EXPECTED_SOLVER_ALL
    assert "find_catalog_build_candidate_with_cp_sat" not in solver_package.__all__
    assert not hasattr(solver_package, "find_catalog_build_candidate_with_cp_sat")


def test_function_signature_is_keyword_only_with_required_defaults() -> None:
    parameters = inspect.signature(find_catalog_build_candidate_with_cp_sat).parameters

    assert tuple(parameters) == (
        "catalog",
        "requirements",
        "weapon_kind",
        "timeout_seconds",
    )
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert parameters["catalog"].default is inspect.Parameter.empty
    assert parameters["requirements"].default is inspect.Parameter.empty
    assert parameters["weapon_kind"].default is None
    assert parameters["timeout_seconds"].default == 10.0


def test_function_rejects_positional_arguments() -> None:
    with pytest.raises(TypeError):
        find_catalog_build_candidate_with_cp_sat(  # type: ignore[misc]
            small_catalog(),
            (),
            None,
            10.0,
        )


def test_catalog_subclass_is_accepted() -> None:
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

    assert isinstance(solve(catalog), BuildCandidate)


@pytest.mark.parametrize("invalid_catalog", [None, object(), {}, ()])
def test_rejects_invalid_catalog_values(invalid_catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        find_catalog_build_candidate_with_cp_sat(
            catalog=invalid_catalog,  # type: ignore[arg-type]
            requirements=(),
        )


@pytest.mark.parametrize(
    "invalid_requirements",
    [
        [requirement("skill:test")],
        {requirement("skill:test")},
        requirement_generator(),
        None,
    ],
)
def test_requirements_must_be_an_exact_tuple(invalid_requirements: object) -> None:
    with pytest.raises(TypeError, match="requirements"):
        find_catalog_build_candidate_with_cp_sat(
            catalog=small_catalog(),
            requirements=invalid_requirements,  # type: ignore[arg-type]
        )


def test_requirements_rejects_tuple_subclass() -> None:
    class RequirementTuple(tuple[SkillRequirement, ...]):
        pass

    with pytest.raises(TypeError, match="requirements"):
        solve(
            small_catalog(),
            RequirementTuple((requirement("skill:test"),)),
        )


@pytest.mark.parametrize("invalid_requirement", [None, "skill:test", object()])
def test_requirements_rejects_invalid_elements(invalid_requirement: object) -> None:
    with pytest.raises(TypeError, match="requirements"):
        find_catalog_build_candidate_with_cp_sat(
            catalog=small_catalog(),
            requirements=(invalid_requirement,),  # type: ignore[arg-type]
        )


def test_requirements_rejects_duplicate_skill_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        solve(
            small_catalog(),
            (requirement("skill:test", 1), requirement("skill:test", 2)),
        )


@pytest.mark.parametrize("weapon_kind", [None, WeaponKind.BOW])
def test_accepts_valid_weapon_kind_values(
    weapon_kind: WeaponKind | None,
) -> None:
    replacements = {
        EquipmentPart.WEAPON: equipment_item(
            EquipmentPart.WEAPON,
            weapon_kind=WeaponKind.BOW,
        )
    }

    assert isinstance(
        solve(
            small_catalog(equipment=complete_equipment(replacements=replacements)),
            weapon_kind=weapon_kind,
        ),
        BuildCandidate,
    )


@pytest.mark.parametrize("invalid_weapon_kind", ["bow", 1, object()])
def test_rejects_invalid_weapon_kind_values(invalid_weapon_kind: object) -> None:
    with pytest.raises(TypeError, match="weapon_kind"):
        find_catalog_build_candidate_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            weapon_kind=invalid_weapon_kind,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("timeout_seconds", [1, 1.0, 0.25])
def test_accepts_positive_int_and_float_timeouts(
    timeout_seconds: int | float,
) -> None:
    assert isinstance(
        solve(small_catalog(), timeout_seconds=timeout_seconds),
        BuildCandidate,
    )


@pytest.mark.parametrize(
    "invalid_timeout",
    [True, False, 0, 0.0, -1, -0.1, float("nan"), float("inf"), float("-inf"), "1"],
)
def test_rejects_invalid_timeout_values(invalid_timeout: object) -> None:
    with pytest.raises((TypeError, ValueError), match="timeout_seconds"):
        find_catalog_build_candidate_with_cp_sat(
            catalog=small_catalog(),
            requirements=(),
            timeout_seconds=invalid_timeout,  # type: ignore[arg-type]
        )


def test_timeout_rejects_numeric_subclasses() -> None:
    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    for invalid_timeout in (IntSubclass(1), FloatSubclass(1.0)):
        with pytest.raises(TypeError, match="timeout_seconds"):
            find_catalog_build_candidate_with_cp_sat(
                catalog=small_catalog(),
                requirements=(),
                timeout_seconds=invalid_timeout,
            )


def test_does_not_mutate_catalog_or_requirements() -> None:
    catalog = small_catalog()
    requirements = (requirement("skill:missing"),)
    original_catalog = catalog
    original_equipment = catalog.equipment
    original_requirements = requirements

    assert solve(catalog, requirements) is None
    assert catalog == original_catalog
    assert catalog.equipment is original_equipment
    assert requirements is original_requirements


def test_empty_requirements_returns_one_complete_build() -> None:
    candidate = solve(small_catalog())

    assert isinstance(candidate, BuildCandidate)
    assert len(candidate.equipment) == len(REQUIRED_PARTS)
    assert Counter(item.part for item in candidate.equipment) == Counter(REQUIRED_PARTS)


def test_selects_exactly_one_candidate_for_each_part_with_multiple_choices() -> None:
    equipment = complete_equipment() + (
        equipment_item(EquipmentPart.HEAD, "equipment:head:second"),
        equipment_item(EquipmentPart.WAIST, "equipment:waist:second"),
    )

    candidate = solve(small_catalog(equipment=equipment))

    assert candidate is not None
    assert Counter(item.part for item in candidate.equipment) == Counter(REQUIRED_PARTS)
    assert sum(item.part is EquipmentPart.HEAD for item in candidate.equipment) == 1
    assert sum(item.part is EquipmentPart.WAIST for item in candidate.equipment) == 1


@pytest.mark.parametrize("missing_part", REQUIRED_PARTS)
def test_missing_equipment_part_returns_none_without_solving(
    monkeypatch: pytest.MonkeyPatch,
    missing_part: EquipmentPart,
) -> None:
    def fail_solve(**_kwargs: object) -> object:
        raise AssertionError("CP-SAT must not be invoked for an empty part pool")

    monkeypatch.setattr(cp_sat_search_module, "_solve_model", fail_solve)
    equipment = tuple(
        item for item in complete_equipment() if item.part is not missing_part
    )

    assert solve(small_catalog(equipment=equipment)) is None


def test_impossible_skill_requirement_returns_none() -> None:
    assert (
        solve(
            small_catalog(),
            (requirement("skill:has-no-contribution"),),
        )
        is None
    )


def test_selected_equipment_follows_equipment_part_declaration_order() -> None:
    catalog = small_catalog(equipment=tuple(reversed(complete_equipment())))

    candidate = solve(catalog)

    assert candidate is not None
    assert tuple(item.part for item in candidate.equipment) == REQUIRED_PARTS


def test_weapon_kind_filter_selects_only_matching_weapon() -> None:
    non_weapons = complete_equipment()[1:]
    equipment = (
        equipment_item(
            EquipmentPart.WEAPON,
            "equipment:weapon:legacy",
        ),
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
        *non_weapons,
    )

    candidate = solve(
        small_catalog(equipment=equipment),
        weapon_kind=WeaponKind.GREAT_SWORD,
    )

    assert candidate is not None
    assert selected_item(candidate, EquipmentPart.WEAPON).equipment_id == (
        "equipment:weapon:great-sword"
    )


def test_selected_weapon_kind_excludes_legacy_weapon_without_kind() -> None:
    assert (
        solve(
            small_catalog(),
            weapon_kind=WeaponKind.GREAT_SWORD,
        )
        is None
    )


def test_fixed_equipment_skill_satisfies_requirement() -> None:
    skilled_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:skilled",
        skills=(contribution("skill:fixed", 2),),
    )
    equipment = complete_equipment() + (skilled_head,)

    candidate = solve(
        small_catalog(equipment=equipment),
        (requirement("skill:fixed", 2),),
    )

    assert candidate is not None
    assert selected_item(candidate, EquipmentPart.HEAD) is skilled_head
    assert dict(candidate.skill_levels)["skill:fixed"] == 2


def test_equipment_candidate_selection_is_repeatable_for_same_input_order() -> None:
    equipment = complete_equipment() + (
        equipment_item(EquipmentPart.HEAD, "equipment:head:second"),
        equipment_item(EquipmentPart.CHEST, "equipment:chest:second"),
    )
    catalog = small_catalog(equipment=equipment)

    candidates = tuple(solve(catalog) for _ in range(4))

    assert candidates[0] is not None
    assert all(candidate == candidates[0] for candidate in candidates[1:])


def test_preprocessing_reuses_helpers_in_required_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    original_filter = cp_sat_search_module.filter_equipment_candidates_by_weapon_kind
    original_generate = (
        cp_sat_search_module.generate_appraisal_charm_equipment_candidates
    )
    original_expand = cp_sat_search_module.expand_equipment_bonus_skill_variants

    def wrapped_filter(**kwargs: object) -> tuple[EquipmentDefinition, ...]:
        calls.append("filter")
        return original_filter(**kwargs)  # type: ignore[arg-type]

    def wrapped_generate(**kwargs: object) -> tuple[EquipmentDefinition, ...]:
        calls.append("generate")
        return original_generate(**kwargs)  # type: ignore[arg-type]

    def wrapped_expand(**kwargs: object) -> tuple[EquipmentDefinition, ...]:
        calls.append("expand")
        expanded_input = kwargs["equipment"]
        assert isinstance(expanded_input, tuple)
        assert expanded_input[-1].equipment_id.startswith("generated:appraisal-charm:")
        return original_expand(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        cp_sat_search_module,
        "filter_equipment_candidates_by_weapon_kind",
        wrapped_filter,
    )
    monkeypatch.setattr(
        cp_sat_search_module,
        "generate_appraisal_charm_equipment_candidates",
        wrapped_generate,
    )
    monkeypatch.setattr(
        cp_sat_search_module,
        "expand_equipment_bonus_skill_variants",
        wrapped_expand,
    )
    skill = normal_skill("skill:appraisal")
    group = appraisal_group(
        "appraisal-group:test",
        skills=(contribution("skill:appraisal"),),
    )
    pattern = appraisal_pattern(
        "appraisal-pattern:test",
        group_ids=(group.group_id,),
    )

    assert (
        solve(
            small_catalog(
                skills=(skill,),
                appraisal_groups=(group,),
                appraisal_patterns=(pattern,),
            )
        )
        is not None
    )
    assert calls == ["filter", "generate", "expand"]


def test_armor_decoration_is_reconstructed_in_armor_slot() -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(armor_slot(2),),
    )
    armor_decoration = decoration(
        "decoration:armor",
        kind=DecorationKind.ARMOR,
        level=2,
        skills=(contribution("skill:armor-decoration"),),
    )

    candidate = solve(
        small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
            decorations=(armor_decoration,),
        ),
        (requirement("skill:armor-decoration"),),
    )

    assert candidate is not None
    assert tuple(
        (placement.equipment_id, placement.slot_index, placement.decoration_id)
        for placement in candidate.placements
    ) == ((head.equipment_id, 0, armor_decoration.decoration_id),)


def test_weapon_decoration_is_reconstructed_in_weapon_slot() -> None:
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        slots=(weapon_slot(1),),
    )
    weapon_decoration = decoration(
        "decoration:weapon",
        kind=DecorationKind.WEAPON,
        skills=(contribution("skill:weapon-decoration"),),
    )

    candidate = solve(
        small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.WEAPON: weapon}),
            decorations=(weapon_decoration,),
        ),
        (requirement("skill:weapon-decoration"),),
    )

    assert candidate is not None
    assert candidate.placements[0].equipment_id == weapon.equipment_id


def test_decoration_kind_mismatch_is_infeasible() -> None:
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        slots=(weapon_slot(3),),
    )
    armor_decoration = decoration(
        "decoration:armor",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:decoration"),),
    )

    assert (
        solve(
            small_catalog(
                equipment=complete_equipment(
                    replacements={EquipmentPart.WEAPON: weapon}
                ),
                decorations=(armor_decoration,),
            ),
            (requirement("skill:decoration"),),
        )
        is None
    )


@pytest.mark.parametrize("available_level", [2, 3])
def test_exact_or_larger_slot_accepts_decoration(available_level: int) -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(armor_slot(available_level),),
    )
    definition = decoration(
        "decoration:level-two",
        kind=DecorationKind.ARMOR,
        level=2,
        skills=(contribution("skill:decoration"),),
    )

    candidate = solve(
        small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
            decorations=(definition,),
        ),
        (requirement("skill:decoration"),),
    )

    assert candidate is not None
    assert candidate.placements[0].decoration_id == definition.decoration_id


def test_insufficient_slot_level_is_infeasible() -> None:
    head = equipment_item(EquipmentPart.HEAD, slots=(armor_slot(1),))
    definition = decoration(
        "decoration:level-two",
        kind=DecorationKind.ARMOR,
        level=2,
        skills=(contribution("skill:decoration"),),
    )

    assert (
        solve(
            small_catalog(
                equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
                decorations=(definition,),
            ),
            (requirement("skill:decoration"),),
        )
        is None
    )


def test_multiple_slots_allow_repeated_copies_of_one_decoration() -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(armor_slot(1), armor_slot(1)),
    )
    definition = decoration(
        "decoration:repeatable",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:repeatable"),),
    )

    candidate = solve(
        small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
            decorations=(definition,),
        ),
        (requirement("skill:repeatable", 2),),
    )

    assert candidate is not None
    assert tuple(p.decoration_id for p in candidate.placements) == (
        definition.decoration_id,
        definition.decoration_id,
    )
    assert tuple(p.slot_index for p in candidate.placements) == (0, 1)


def test_compound_decoration_contributes_all_of_its_skills() -> None:
    head = equipment_item(EquipmentPart.HEAD, slots=(armor_slot(1),))
    compound = decoration(
        "decoration:compound",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:first"), contribution("skill:second", 2)),
    )
    requirements = (
        requirement("skill:first"),
        requirement("skill:second", 2),
    )

    candidate = solve(
        small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
            decorations=(compound,),
        ),
        requirements,
    )

    assert candidate is not None
    assert candidate.placements[0].decoration_id == compound.decoration_id
    assert skill_levels_satisfy_requirements(
        skill_levels=dict(candidate.skill_levels),
        requirements=requirements,
    )


def test_threshold_constraints_reserve_high_level_slots() -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(armor_slot(3), armor_slot(1)),
    )
    high = decoration(
        "decoration:high",
        kind=DecorationKind.ARMOR,
        level=3,
        skills=(contribution("skill:high"),),
    )

    assert (
        solve(
            small_catalog(
                equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
                decorations=(high,),
            ),
            (requirement("skill:high", 2),),
        )
        is None
    )


def test_slot_capacity_only_uses_the_selected_equipment_candidate() -> None:
    required_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:required",
        skills=(contribution("skill:forces-head"),),
    )
    slotted_head = equipment_item(
        EquipmentPart.HEAD,
        "equipment:head:slotted",
        slots=(armor_slot(1),),
    )
    definition = decoration(
        "decoration:only-on-other-head",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:decorated"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: required_head})
        + (slotted_head,),
        decorations=(definition,),
    )

    assert (
        solve(
            catalog,
            (requirement("skill:forces-head"), requirement("skill:decorated")),
        )
        is None
    )


def test_equipment_only_solution_minimizes_to_zero_decorations() -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        skills=(contribution("skill:shared"),),
        slots=(armor_slot(1),),
    )
    definition = decoration(
        "decoration:shared",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:shared"),),
    )

    candidate = solve(
        small_catalog(
            equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
            decorations=(definition,),
        ),
        (requirement("skill:shared"),),
    )

    assert candidate is not None
    assert candidate.placements == ()


def test_returned_placements_pass_existing_build_validation() -> None:
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        slots=(weapon_slot(1),),
    )
    definition = decoration(
        "decoration:valid",
        kind=DecorationKind.WEAPON,
        skills=(contribution("skill:valid"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.WEAPON: weapon}),
        decorations=(definition,),
    )

    candidate = solve(catalog, (requirement("skill:valid"),))

    assert candidate is not None
    assert validate_build(
        equipment=candidate.equipment,
        decorations=catalog.decorations,
        placements=candidate.placements,
    ) == BuildValidationResult((), ())


def test_placement_matching_and_output_order_are_deterministic() -> None:
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        slots=(weapon_slot(3), weapon_slot(1)),
    )
    low = decoration(
        "decoration:low",
        kind=DecorationKind.WEAPON,
        level=1,
        skills=(contribution("skill:low"),),
    )
    high = decoration(
        "decoration:high",
        kind=DecorationKind.WEAPON,
        level=3,
        skills=(contribution("skill:high"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.WEAPON: weapon}),
        decorations=(low, high),
    )
    requirements = (requirement("skill:low"), requirement("skill:high"))

    first = solve(catalog, requirements)
    second = solve(catalog, requirements)

    assert first is not None
    assert second == first
    assert tuple(
        (placement.slot_index, placement.decoration_id)
        for placement in first.placements
    ) == ((0, high.decoration_id), (1, low.decoration_id))


def test_catalog_decoration_order_breaks_equal_level_placement_ties() -> None:
    head = equipment_item(EquipmentPart.HEAD, slots=(armor_slot(1), armor_slot(1)))
    first = decoration(
        "decoration:first",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:first"),),
    )
    second = decoration(
        "decoration:second",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:second"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
        decorations=(first, second),
    )

    candidate = solve(
        catalog,
        (requirement("skill:first"), requirement("skill:second")),
    )

    assert candidate is not None
    assert tuple(
        (placement.slot_index, placement.decoration_id)
        for placement in candidate.placements
    ) == ((0, first.decoration_id), (1, second.decoration_id))


def test_series_bonus_can_satisfy_requirement() -> None:
    series_id = "skill:series"
    replacements = {
        part: equipment_item(part, series_skill_id=series_id)
        for part in (EquipmentPart.HEAD, EquipmentPart.CHEST)
    }
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements),
        skills=(bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(2, 4)),),
    )

    candidate = solve(catalog, (requirement(series_id),))

    assert candidate is not None
    assert dict(candidate.skill_levels)[series_id] == 1


def test_group_bonus_can_satisfy_requirement() -> None:
    group_id = "skill:group"
    replacements = {
        part: equipment_item(part, group_skill_id=group_id)
        for part in (EquipmentPart.HEAD, EquipmentPart.CHEST, EquipmentPart.ARMS)
    }
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements),
        skills=(bonus_skill(group_id, kind=SkillKind.GROUP, thresholds=(3,)),),
    )

    candidate = solve(catalog, (requirement(group_id),))

    assert candidate is not None
    assert dict(candidate.skill_levels)[group_id] == 1


def test_highest_activated_bonus_rank_is_returned() -> None:
    series_id = "skill:series"
    replacements = {
        part: equipment_item(part, series_skill_id=series_id)
        for part in (
            EquipmentPart.HEAD,
            EquipmentPart.CHEST,
            EquipmentPart.ARMS,
            EquipmentPart.WAIST,
        )
    }
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements),
        skills=(bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(2, 4)),),
    )

    candidate = solve(catalog, (requirement(series_id, 2),))

    assert candidate is not None
    assert dict(candidate.skill_levels)[series_id] == 2


def test_bonus_rank_cannot_activate_below_its_piece_threshold() -> None:
    series_id = "skill:series"
    replacements = {
        part: equipment_item(part, series_skill_id=series_id)
        for part in (EquipmentPart.HEAD, EquipmentPart.CHEST, EquipmentPart.ARMS)
    }
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements),
        skills=(bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(2, 4)),),
    )

    assert solve(catalog, (requirement(series_id, 2),)) is None


def test_fixed_contribution_is_added_to_activated_bonus_level() -> None:
    series_id = "skill:series"
    replacements = {
        EquipmentPart.HEAD: equipment_item(
            EquipmentPart.HEAD,
            skills=(contribution(series_id),),
            series_skill_id=series_id,
        ),
        EquipmentPart.CHEST: equipment_item(
            EquipmentPart.CHEST,
            series_skill_id=series_id,
        ),
    }
    catalog = small_catalog(
        equipment=complete_equipment(replacements=replacements),
        skills=(bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(2,)),),
    )

    candidate = solve(catalog, (requirement(series_id, 2),))

    assert candidate is not None
    assert dict(candidate.skill_levels)[series_id] == 2


def test_decoration_contribution_is_added_to_activated_bonus_level() -> None:
    series_id = "skill:series"
    head = equipment_item(
        EquipmentPart.HEAD,
        slots=(armor_slot(1),),
        series_skill_id=series_id,
    )
    chest = equipment_item(
        EquipmentPart.CHEST,
        series_skill_id=series_id,
    )
    definition = decoration(
        "decoration:series",
        kind=DecorationKind.ARMOR,
        skills=(contribution(series_id),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={
                EquipmentPart.HEAD: head,
                EquipmentPart.CHEST: chest,
            }
        ),
        decorations=(definition,),
        skills=(bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(2,)),),
    )

    candidate = solve(catalog, (requirement(series_id, 2),))

    assert candidate is not None
    assert len(candidate.placements) == 1
    assert dict(candidate.skill_levels)[series_id] == 2


def test_artian_series_and_group_variant_can_satisfy_requirements() -> None:
    series_id = "skill:artian-series"
    group_id = "skill:artian-group"
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        "equipment:weapon:artian",
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.WEAPON: weapon}),
        skills=(
            bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(1,)),
            bonus_skill(group_id, kind=SkillKind.GROUP, thresholds=(1,)),
        ),
    )

    candidate = solve(
        catalog,
        (requirement(series_id), requirement(group_id)),
    )

    assert candidate is not None
    selected_weapon = selected_item(candidate, EquipmentPart.WEAPON)
    assert selected_weapon.series_skill_id == series_id
    assert selected_weapon.group_skill_id == group_id
    assert selected_weapon.allows_series_skill_assignment is False
    assert selected_weapon.allows_group_skill_assignment is False


def test_artian_variants_with_duplicate_equipment_ids_remain_distinct() -> None:
    first_series_id = "skill:artian-series-first"
    second_series_id = "skill:artian-series-second"
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        "equipment:weapon:artian-shared-id",
        allows_series_skill_assignment=True,
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.WEAPON: weapon}),
        skills=(
            bonus_skill(first_series_id, kind=SkillKind.SERIES, thresholds=(1,)),
            bonus_skill(second_series_id, kind=SkillKind.SERIES, thresholds=(1,)),
        ),
    )

    candidate = solve(catalog, (requirement(second_series_id),))

    assert candidate is not None
    selected_weapon = selected_item(candidate, EquipmentPart.WEAPON)
    assert selected_weapon.equipment_id == weapon.equipment_id
    assert selected_weapon.series_skill_id == second_series_id
    assert validate_build(
        equipment=candidate.equipment,
        decorations=catalog.decorations,
        placements=candidate.placements,
    ) == BuildValidationResult((), ())


def test_weapon_kind_filtering_happens_before_artian_expansion() -> None:
    series_id = "skill:artian-series"
    weapons = (
        equipment_item(
            EquipmentPart.WEAPON,
            "equipment:weapon:great-sword-artian",
            allows_series_skill_assignment=True,
            weapon_kind=WeaponKind.GREAT_SWORD,
        ),
        equipment_item(
            EquipmentPart.WEAPON,
            "equipment:weapon:bow-artian",
            allows_series_skill_assignment=True,
            weapon_kind=WeaponKind.BOW,
        ),
    )
    catalog = small_catalog(
        equipment=weapons + complete_equipment()[1:],
        skills=(bonus_skill(series_id, kind=SkillKind.SERIES, thresholds=(1,)),),
    )

    candidate = solve(
        catalog,
        (requirement(series_id),),
        weapon_kind=WeaponKind.BOW,
    )

    assert candidate is not None
    assert selected_item(candidate, EquipmentPart.WEAPON).weapon_kind is WeaponKind.BOW


def test_generated_appraisal_charm_can_satisfy_requirement() -> None:
    skill_id = "skill:appraisal"
    group = appraisal_group(
        "appraisal-group:test",
        skills=(contribution(skill_id),),
    )
    pattern = appraisal_pattern(
        "appraisal-pattern:test",
        group_ids=(group.group_id,),
    )
    catalog = small_catalog(
        skills=(normal_skill(skill_id),),
        appraisal_groups=(group,),
        appraisal_patterns=(pattern,),
    )

    candidate = solve(catalog, (requirement(skill_id),))

    assert candidate is not None
    assert selected_item(candidate, EquipmentPart.CHARM).equipment_id.startswith(
        "generated:appraisal-charm:"
    )


def test_repeated_selected_appraisal_skill_is_aggregated_once() -> None:
    skill_id = "skill:repeated-appraisal"
    group = appraisal_group(
        "appraisal-group:repeat",
        skills=(contribution(skill_id),),
    )
    pattern = appraisal_pattern(
        "appraisal-pattern:repeat",
        group_ids=(group.group_id, group.group_id),
    )
    catalog = small_catalog(
        skills=(normal_skill(skill_id, maximum_level=2),),
        appraisal_groups=(group,),
        appraisal_patterns=(pattern,),
    )

    candidate = solve(catalog, (requirement(skill_id, 2),))

    assert candidate is not None
    charm = selected_item(candidate, EquipmentPart.CHARM)
    assert charm.skills == (contribution(skill_id, 2),)
    assert candidate.skill_levels.count((skill_id, 2)) == 1


def test_fixed_charm_candidate_remains_usable() -> None:
    fixed_charm = equipment_item(
        EquipmentPart.CHARM,
        "equipment:charm:fixed",
        skills=(contribution("skill:fixed-charm"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.CHARM: fixed_charm})
    )

    candidate = solve(catalog, (requirement("skill:fixed-charm"),))

    assert candidate is not None
    assert selected_item(candidate, EquipmentPart.CHARM) is fixed_charm


def test_generated_appraisal_charm_id_collision_still_fails() -> None:
    skill_id = "skill:appraisal"
    group = appraisal_group(
        "appraisal-group:collision",
        skills=(contribution(skill_id),),
    )
    pattern = appraisal_pattern(
        "appraisal-pattern:collision",
        group_ids=(group.group_id,),
    )
    collision_id = (
        "generated:appraisal-charm:rarity-8:appraisal-pattern:collision:combination-1"
    )
    stored_charm = equipment_item(EquipmentPart.CHARM, collision_id)
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.CHARM: stored_charm}),
        skills=(normal_skill(skill_id),),
        appraisal_groups=(group,),
        appraisal_patterns=(pattern,),
    )

    with pytest.raises(ValueError, match="equipment"):
        solve(catalog)


def test_returned_candidate_is_valid_and_satisfies_all_requirements() -> None:
    head = equipment_item(
        EquipmentPart.HEAD,
        skills=(contribution("skill:fixed"),),
        slots=(armor_slot(1),),
    )
    definition = decoration(
        "decoration:required",
        kind=DecorationKind.ARMOR,
        skills=(contribution("skill:decorated"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(replacements={EquipmentPart.HEAD: head}),
        decorations=(definition,),
    )
    requirements = (
        requirement("skill:fixed"),
        requirement("skill:decorated"),
    )

    candidate = solve(catalog, requirements)

    assert isinstance(candidate, BuildCandidate)
    assert validate_build(
        equipment=candidate.equipment,
        decorations=catalog.decorations,
        placements=candidate.placements,
    ) == BuildValidationResult((), ())
    assert skill_levels_satisfy_requirements(
        skill_levels=dict(candidate.skill_levels),
        requirements=requirements,
    )


def test_skill_level_order_is_stable() -> None:
    weapon = equipment_item(
        EquipmentPart.WEAPON,
        skills=(contribution("skill:weapon-first"),),
        slots=(weapon_slot(1),),
    )
    head = equipment_item(
        EquipmentPart.HEAD,
        skills=(contribution("skill:head-second"),),
    )
    definition = decoration(
        "decoration:third",
        kind=DecorationKind.WEAPON,
        skills=(contribution("skill:decoration-third"),),
    )
    catalog = small_catalog(
        equipment=complete_equipment(
            replacements={
                EquipmentPart.WEAPON: weapon,
                EquipmentPart.HEAD: head,
            }
        ),
        decorations=(definition,),
    )

    candidate = solve(catalog, (requirement("skill:decoration-third"),))

    assert candidate is not None
    assert candidate.skill_levels == (
        ("skill:weapon-first", 1),
        ("skill:head-second", 1),
        ("skill:decoration-third", 1),
    )


def test_repeated_identical_calls_return_equal_candidates() -> None:
    catalog = small_catalog()

    assert solve(catalog) == solve(catalog) == solve(catalog)


def test_cp_sat_path_does_not_call_exhaustive_enumerators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("exhaustive enumeration must not be used")

    monkeypatch.setattr(build_module, "enumerate_build_candidates", fail)
    monkeypatch.setattr(equipment_solver_module, "enumerate_equipment_selections", fail)
    monkeypatch.setattr(
        decoration_solver_module,
        "enumerate_decoration_placement_combinations",
        fail,
    )

    assert isinstance(solve(small_catalog()), BuildCandidate)


def test_unknown_solver_status_raises_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cp_sat_search_module,
        "_solve_model",
        lambda **_kwargs: (object(), cp_model.UNKNOWN),
    )

    with pytest.raises(TimeoutError, match="timeout"):
        solve(small_catalog())


def test_model_invalid_solver_status_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cp_sat_search_module,
        "_solve_model",
        lambda **_kwargs: (object(), cp_model.MODEL_INVALID),
    )

    with pytest.raises(RuntimeError, match="model"):
        solve(small_catalog())


def test_unexpected_solver_status_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cp_sat_search_module,
        "_solve_model",
        lambda **_kwargs: (object(), -999),
    )

    with pytest.raises(RuntimeError):
        solve(small_catalog())
