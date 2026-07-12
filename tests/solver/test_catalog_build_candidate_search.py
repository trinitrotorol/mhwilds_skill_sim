from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from mhwilds_skill_sim.catalog.loader import load_catalog
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
from mhwilds_skill_sim.solver import (
    BuildCandidate,
    SkillRequirement,
    enumerate_build_candidates,
    enumerate_decoration_placement_combinations,
    enumerate_equipment_selections,
    filter_build_candidates_by_skill_requirements,
    search_build_candidates_by_skill_requirements,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.solver.catalog_search import (
    search_catalog_build_candidates_by_skill_requirements,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "data" / "fixtures" / "tiny_catalog.json"

REQUIRED_PARTS = (
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
)


class CatalogSubclass(Catalog):
    pass


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def equipment_definition(
    part: EquipmentPart,
    equipment_id: str | None = None,
    *,
    skills: tuple[SkillContribution, ...] = (),
    slots: tuple[DecorationSlot, ...] = (),
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
    weapon_kind: WeaponKind | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=slots,
        allows_series_skill_assignment=allows_series_skill_assignment,
        allows_group_skill_assignment=allows_group_skill_assignment,
        weapon_kind=weapon_kind,
    )


def complete_equipment(
    *,
    weapon_skills: tuple[SkillContribution, ...] = (),
    weapon_slots: tuple[DecorationSlot, ...] = (),
    weapon_kind: WeaponKind | None = None,
) -> tuple[EquipmentDefinition, ...]:
    return tuple(
        equipment_definition(
            part,
            skills=weapon_skills if part is EquipmentPart.WEAPON else (),
            slots=weapon_slots if part is EquipmentPart.WEAPON else (),
            weapon_kind=weapon_kind if part is EquipmentPart.WEAPON else None,
        )
        for part in REQUIRED_PARTS
    )


def decoration_definition(
    decoration_id: str = "decoration:weapon-1",
    *,
    required_slot: DecorationSlot | None = None,
    skills: tuple[SkillContribution, ...] | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=required_slot or weapon_slot(1),
        skills=skills or (skill("skill:decoration-default", 1),),
    )


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def tiny_catalog() -> Catalog:
    return load_catalog(path=FIXTURE_PATH)


def weapon_kind_catalog(*, catalog_type: type[Catalog] = Catalog) -> Catalog:
    base_equipment = complete_equipment(weapon_kind=WeaponKind.GREAT_SWORD)
    return catalog_type(
        schema_version=1,
        equipment=(
            base_equipment[0],
            equipment_definition(
                EquipmentPart.WEAPON,
                "equipment:bow",
                weapon_kind=WeaponKind.BOW,
            ),
            base_equipment[1],
            equipment_definition(EquipmentPart.HEAD, "equipment:head-alternate"),
            *base_equipment[2:],
        ),
        decorations=(),
    )


def weapon_kind_artian_appraisal_catalog() -> Catalog:
    skills = (
        SkillDefinition(
            skill_id="skill:series-bonus",
            kind=SkillKind.SERIES,
            ranks=(SkillRankDefinition(level=1, required_pieces=1),),
        ),
        SkillDefinition(
            skill_id="skill:group-bonus",
            kind=SkillKind.GROUP,
            ranks=(SkillRankDefinition(level=1, required_pieces=1),),
        ),
        SkillDefinition(
            skill_id="skill:attack-boost",
            kind=SkillKind.ARMOR,
            ranks=(SkillRankDefinition(level=1, required_pieces=None),),
        ),
    )
    base_equipment = complete_equipment()
    return Catalog(
        schema_version=1,
        equipment=(
            equipment_definition(
                EquipmentPart.WEAPON,
                "equipment:great-sword-artian",
                allows_series_skill_assignment=True,
                allows_group_skill_assignment=True,
                weapon_kind=WeaponKind.GREAT_SWORD,
            ),
            equipment_definition(
                EquipmentPart.WEAPON,
                "equipment:bow-artian",
                allows_series_skill_assignment=True,
                allows_group_skill_assignment=True,
                weapon_kind=WeaponKind.BOW,
            ),
            *base_equipment[1:],
        ),
        decorations=(),
        skills=skills,
        appraisal_charm_skill_groups=(
            AppraisalCharmSkillGroupDefinition(
                group_id="appraisal-group:A",
                skills=(skill("skill:attack-boost", 1),),
            ),
        ),
        appraisal_charm_patterns=(
            AppraisalCharmPatternDefinition(
                pattern_id="appraisal-pattern:r8-a",
                rarity=8,
                skill_group_ids=("appraisal-group:A",),
                slots=(),
            ),
        ),
    )


def catalog_search(
    *,
    catalog: Catalog,
    requirements: tuple[SkillRequirement, ...],
    weapon_kind: WeaponKind | None = None,
) -> tuple[BuildCandidate, ...]:
    return search_catalog_build_candidates_by_skill_requirements(
        catalog=catalog,
        requirements=requirements,
        weapon_kind=weapon_kind,
    )


def selected_head_id(candidate: BuildCandidate) -> str:
    return next(
        equipment.equipment_id
        for equipment in candidate.equipment
        if equipment.part is EquipmentPart.HEAD
    )


def selected_weapon(candidate: BuildCandidate) -> EquipmentDefinition:
    return next(
        equipment
        for equipment in candidate.equipment
        if equipment.part is EquipmentPart.WEAPON
    )


def selected_charm(candidate: BuildCandidate) -> EquipmentDefinition:
    return next(
        equipment
        for equipment in candidate.equipment
        if equipment.part is EquipmentPart.CHARM
    )


def test_empty_catalog_and_empty_requirements_returns_empty_tuple() -> None:
    catalog = Catalog(schema_version=1, equipment=(), decorations=())

    assert catalog_search(catalog=catalog, requirements=()) == ()


def test_tiny_catalog_empty_requirements_returns_candidates() -> None:
    catalog = tiny_catalog()

    result = catalog_search(catalog=catalog, requirements=())

    assert len(result) > 0
    assert result == search_build_candidates_by_skill_requirements(
        equipment=catalog.equipment,
        decorations=catalog.decorations,
        requirements=(),
        skill_definitions=catalog.skills,
        appraisal_charm_skill_groups=catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=catalog.appraisal_charm_patterns,
    )


def test_all_tiny_catalog_candidates_expose_expected_bonus_levels() -> None:
    result = catalog_search(catalog=tiny_catalog(), requirements=())

    assert result
    for candidate in result:
        skill_levels = dict(candidate.skill_levels)
        assert selected_head_id(candidate) in {
            "fixture:head:precision-alpha",
            "fixture:head:tenderizer-beta",
        }
        assert skill_levels["skill:fixture-series-bonus"] == 2
        assert skill_levels["skill:fixture-group-bonus"] == 1


def test_all_tiny_catalog_candidates_contain_resolved_training_blade_variant() -> None:
    result = catalog_search(catalog=tiny_catalog(), requirements=())

    assert result
    for candidate in result:
        weapon = selected_weapon(candidate)
        assert weapon.equipment_id == "fixture:weapon:training-blade"
        assert weapon.series_skill_id == "skill:fixture-series-bonus"
        assert weapon.group_skill_id == "skill:fixture-group-bonus"
        assert weapon.allows_series_skill_assignment is False
        assert weapon.allows_group_skill_assignment is False


def test_series_level_two_requirement_includes_both_head_routes() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:fixture-series-bonus", 2),),
    )

    assert result
    assert {selected_head_id(candidate) for candidate in result} == {
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
    }


def test_group_level_one_requirement_includes_both_head_routes() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:fixture-group-bonus", 1),),
    )

    assert result
    assert {selected_head_id(candidate) for candidate in result} == {
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
    }


def test_series_level_one_requirement_includes_both_head_routes() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:fixture-series-bonus", 1),),
    )

    assert {selected_head_id(candidate) for candidate in result} == {
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
    }


def test_beta_head_empty_placement_candidate_has_artian_boosted_bonuses() -> None:
    candidate = next(
        candidate
        for candidate in catalog_search(catalog=tiny_catalog(), requirements=())
        if selected_head_id(candidate) == "fixture:head:tenderizer-beta"
        and candidate.placements == ()
    )

    assert dict(candidate.skill_levels)["skill:fixture-series-bonus"] == 2
    assert dict(candidate.skill_levels)["skill:fixture-group-bonus"] == 1


def test_alpha_head_empty_placement_candidate_has_both_bonus_skills() -> None:
    candidate = next(
        candidate
        for candidate in catalog_search(catalog=tiny_catalog(), requirements=())
        if selected_head_id(candidate) == "fixture:head:precision-alpha"
        and candidate.placements == ()
    )

    assert dict(candidate.skill_levels)["skill:fixture-series-bonus"] == 2
    assert dict(candidate.skill_levels)["skill:fixture-group-bonus"] == 1


def test_tiny_catalog_equipment_skills_can_satisfy_requirements() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:attack-boost", 3),),
    )

    assert any(
        build.placements == () and dict(build.skill_levels)["skill:attack-boost"] >= 3
        for build in result
    )


def test_tiny_catalog_decoration_skills_can_satisfy_requirements() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:weakness-exploit", 4),),
    )

    assert len(result) > 0
    assert all(
        dict(build.skill_levels)["skill:weakness-exploit"] >= 4 for build in result
    )
    assert any(
        "fixture:decoration:armor-tenderizer-2"
        in tuple(placement.decoration_id for placement in build.placements)
        for build in result
    )


def test_tiny_catalog_unsatisfied_requirements_return_empty_tuple() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:not-present", 1),),
    )

    assert result == ()


def test_multiple_requirements_must_all_be_satisfied() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(
            requirement("skill:attack-boost", 3),
            requirement("skill:critical-eye", 3),
        ),
    )

    assert len(result) > 0
    assert all(
        dict(build.skill_levels)["skill:attack-boost"] >= 3
        and dict(build.skill_levels)["skill:critical-eye"] >= 3
        for build in result
    )


def test_result_order_matches_existing_search_order() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:critical-eye", 3),)

    result = catalog_search(catalog=catalog, requirements=requirements)
    direct_result = search_build_candidates_by_skill_requirements(
        equipment=catalog.equipment,
        decorations=catalog.decorations,
        requirements=requirements,
        skill_definitions=catalog.skills,
        appraisal_charm_skill_groups=catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=catalog.appraisal_charm_patterns,
    )

    assert result == direct_result


def test_default_weapon_kind_keeps_all_catalog_weapons() -> None:
    catalog = weapon_kind_catalog()

    omitted = catalog_search(catalog=catalog, requirements=())
    explicit_none = catalog_search(
        catalog=catalog,
        requirements=(),
        weapon_kind=None,
    )

    assert omitted == explicit_none
    assert tuple(selected_weapon(candidate).weapon_kind for candidate in omitted) == (
        WeaponKind.GREAT_SWORD,
        WeaponKind.GREAT_SWORD,
        WeaponKind.BOW,
        WeaponKind.BOW,
    )


@pytest.mark.parametrize(
    ("weapon_kind", "expected_weapon_id"),
    [
        (WeaponKind.GREAT_SWORD, "equipment:weapon"),
        (WeaponKind.BOW, "equipment:bow"),
    ],
)
def test_catalog_weapon_kind_selects_matching_weapon_and_keeps_armor_choices(
    weapon_kind: WeaponKind,
    expected_weapon_id: str,
) -> None:
    result = catalog_search(
        catalog=weapon_kind_catalog(),
        requirements=(),
        weapon_kind=weapon_kind,
    )

    assert len(result) == 2
    assert all(
        selected_weapon(candidate).equipment_id == expected_weapon_id
        and selected_weapon(candidate).weapon_kind is weapon_kind
        for candidate in result
    )
    assert {selected_head_id(candidate) for candidate in result} == {
        "equipment:head",
        "equipment:head-alternate",
    }
    assert all(
        {equipment.part for equipment in candidate.equipment} == set(REQUIRED_PARTS)
        for candidate in result
    )


def test_catalog_weapon_kind_search_matches_direct_search_with_same_kind() -> None:
    catalog = weapon_kind_catalog()

    catalog_result = catalog_search(
        catalog=catalog,
        requirements=(),
        weapon_kind=WeaponKind.BOW,
    )
    direct_result = search_build_candidates_by_skill_requirements(
        equipment=catalog.equipment,
        decorations=catalog.decorations,
        requirements=(),
        weapon_kind=WeaponKind.BOW,
        skill_definitions=catalog.skills,
        appraisal_charm_skill_groups=catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=catalog.appraisal_charm_patterns,
    )

    assert catalog_result == direct_result


def test_catalog_subclass_preserves_weapon_kind_filtering() -> None:
    result = catalog_search(
        catalog=weapon_kind_catalog(catalog_type=CatalogSubclass),
        requirements=(),
        weapon_kind=WeaponKind.BOW,
    )

    assert len(result) == 2
    assert all(
        selected_weapon(candidate).weapon_kind is WeaponKind.BOW for candidate in result
    )


def test_weapon_kind_filter_preserves_artian_and_appraisal_generation() -> None:
    result = catalog_search(
        catalog=weapon_kind_artian_appraisal_catalog(),
        requirements=(),
        weapon_kind=WeaponKind.GREAT_SWORD,
    )

    assert len(result) == 2
    assert all(
        selected_weapon(candidate).equipment_id == "equipment:great-sword-artian"
        and selected_weapon(candidate).weapon_kind is WeaponKind.GREAT_SWORD
        and selected_weapon(candidate).series_skill_id == "skill:series-bonus"
        and selected_weapon(candidate).group_skill_id == "skill:group-bonus"
        and selected_weapon(candidate).allows_series_skill_assignment is False
        and selected_weapon(candidate).allows_group_skill_assignment is False
        for candidate in result
    )
    assert selected_charm(result[0]).equipment_id == "equipment:charm"
    assert selected_charm(result[1]).equipment_id.startswith(
        "generated:appraisal-charm:"
    )


def test_returns_tuple_with_build_candidate_elements() -> None:
    result = catalog_search(catalog=tiny_catalog(), requirements=())

    assert type(result) is tuple
    assert all(isinstance(build, BuildCandidate) for build in result)


def test_search_requires_keyword_arguments() -> None:
    signature = inspect.signature(search_catalog_build_candidates_by_skill_requirements)

    assert signature.parameters["catalog"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["requirements"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["weapon_kind"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["weapon_kind"].default is None

    with pytest.raises(TypeError):
        search_catalog_build_candidates_by_skill_requirements(tiny_catalog(), ())  # type: ignore[call-arg]


def test_inputs_are_not_modified() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:attack-boost", 3),)
    original_catalog = catalog
    original_equipment = catalog.equipment
    original_decorations = catalog.decorations
    original_requirements = requirements

    catalog_search(catalog=catalog, requirements=requirements)

    assert catalog == original_catalog
    assert catalog.equipment == original_equipment
    assert catalog.decorations == original_decorations
    assert requirements == original_requirements


def test_solver_package_exports_catalog_search_and_keeps_existing_public_exports() -> (
    None
):
    from mhwilds_skill_sim.solver import BuildCandidate as ExportedBuildCandidate
    from mhwilds_skill_sim.solver import SkillRequirement as ExportedRequirement
    from mhwilds_skill_sim.solver import (
        enumerate_build_candidates as exported_builds,
    )
    from mhwilds_skill_sim.solver import (
        enumerate_decoration_placement_combinations as exported_decorations,
    )
    from mhwilds_skill_sim.solver import (
        enumerate_equipment_selections as exported_equipment,
    )
    from mhwilds_skill_sim.solver import (
        filter_build_candidates_by_skill_requirements as exported_filter,
    )
    from mhwilds_skill_sim.solver import (
        search_build_candidates_by_skill_requirements as exported_search,
    )
    from mhwilds_skill_sim.solver import (
        search_catalog_build_candidates_by_skill_requirements as exported_catalog_search,
    )
    from mhwilds_skill_sim.solver import (
        skill_levels_satisfy_requirements as exported_requirements,
    )

    assert ExportedBuildCandidate is BuildCandidate
    assert ExportedRequirement is SkillRequirement
    assert exported_builds is enumerate_build_candidates
    assert exported_decorations is enumerate_decoration_placement_combinations
    assert exported_equipment is enumerate_equipment_selections
    assert exported_filter is filter_build_candidates_by_skill_requirements
    assert exported_search is search_build_candidates_by_skill_requirements
    assert (
        exported_catalog_search is search_catalog_build_candidates_by_skill_requirements
    )
    assert exported_requirements is skill_levels_satisfy_requirements


def test_delegates_to_existing_search_with_catalog_contents() -> None:
    catalog = tiny_catalog()
    requirements = (requirement("skill:weakness-exploit", 4),)

    assert catalog_search(catalog=catalog, requirements=requirements) == (
        search_build_candidates_by_skill_requirements(
            equipment=catalog.equipment,
            decorations=catalog.decorations,
            requirements=requirements,
            skill_definitions=catalog.skills,
            appraisal_charm_skill_groups=catalog.appraisal_charm_skill_groups,
            appraisal_charm_patterns=catalog.appraisal_charm_patterns,
        )
    )


@pytest.mark.parametrize("catalog", ["catalog", {}, None])
def test_rejects_non_catalog_values(catalog: object) -> None:
    with pytest.raises(TypeError, match="catalog"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=catalog,  # type: ignore[arg-type]
            requirements=(),
        )


def test_propagates_invalid_weapon_kind_type_error() -> None:
    with pytest.raises(TypeError, match="weapon_kind"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=weapon_kind_catalog(),
            requirements=(),
            weapon_kind="bow",  # type: ignore[arg-type]
        )


def test_accepts_catalog_subclass() -> None:
    catalog = CatalogSubclass(schema_version=1, equipment=(), decorations=())

    assert catalog_search(catalog=catalog, requirements=()) == ()


def test_catalog_subclass_uses_bonus_skill_definitions() -> None:
    base_catalog = tiny_catalog()
    catalog = CatalogSubclass(
        schema_version=base_catalog.schema_version,
        equipment=base_catalog.equipment,
        decorations=base_catalog.decorations,
        skills=base_catalog.skills,
        appraisal_charm_skill_groups=base_catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=base_catalog.appraisal_charm_patterns,
    )

    result = catalog_search(
        catalog=catalog,
        requirements=(requirement("skill:fixture-group-bonus", 1),),
    )

    assert result
    assert {selected_head_id(candidate) for candidate in result} == {
        "fixture:head:precision-alpha",
        "fixture:head:tenderizer-beta",
    }


def test_propagates_requirement_list_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=[requirement()],  # type: ignore[arg-type]
        )


def test_propagates_invalid_requirement_element_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=("skill:attack-boost",),  # type: ignore[arg-type]
        )


def test_propagates_duplicate_requirement_skill_id_value_error() -> None:
    with pytest.raises(ValueError, match="requirements"):
        search_catalog_build_candidates_by_skill_requirements(
            catalog=tiny_catalog(),
            requirements=(
                requirement("skill:attack-boost", 1),
                requirement("skill:attack-boost", 2),
            ),
        )


def test_manual_catalog_search_does_not_require_load_catalog() -> None:
    catalog = Catalog(
        schema_version=1,
        equipment=complete_equipment(weapon_skills=(skill("skill:attack-boost", 1),)),
        decorations=(),
    )

    result = catalog_search(
        catalog=catalog,
        requirements=(requirement("skill:attack-boost", 1),),
    )

    assert len(result) == 1
    assert result[0].equipment == catalog.equipment


def test_search_does_not_rank_or_limit_satisfying_candidates() -> None:
    catalog = tiny_catalog()
    result = catalog_search(
        catalog=catalog,
        requirements=(requirement("skill:attack-boost", 3),),
    )

    assert len(result) > 1
    assert result == search_build_candidates_by_skill_requirements(
        equipment=catalog.equipment,
        decorations=catalog.decorations,
        requirements=(requirement("skill:attack-boost", 3),),
        skill_definitions=catalog.skills,
        appraisal_charm_skill_groups=catalog.appraisal_charm_skill_groups,
        appraisal_charm_patterns=catalog.appraisal_charm_patterns,
    )


def test_search_adds_no_request_or_result_public_types() -> None:
    import mhwilds_skill_sim.solver as solver
    import mhwilds_skill_sim.solver.catalog_search as catalog_search_module

    for name in ("SearchRequest", "SolverResult", "BuildResult"):
        assert not hasattr(solver, name)
        assert not hasattr(catalog_search_module, name)


def test_fixture_search_contains_exact_generated_and_fixed_charm_pool() -> None:
    result = catalog_search(catalog=tiny_catalog(), requirements=())
    expected_generated_ids = [
        (
            "generated:appraisal-charm:rarity-8:"
            "fixture:appraisal-pattern:r8-b-a-j-w1-a1-a1:combination-1"
        ),
        (
            "generated:appraisal-charm:rarity-8:"
            "fixture:appraisal-pattern:r8-b-a-j-w1-a1-a1:combination-2"
        ),
        (
            "generated:appraisal-charm:rarity-8:"
            "fixture:appraisal-pattern:r8-b-a-j-w1-a1-a1:combination-3"
        ),
        (
            "generated:appraisal-charm:rarity-8:"
            "fixture:appraisal-pattern:r8-b-a-j-w1-a1-a1:combination-4"
        ),
        (
            "generated:appraisal-charm:rarity-8:"
            "fixture:appraisal-pattern:r8-b-j-w1-a1:combination-1"
        ),
        (
            "generated:appraisal-charm:rarity-8:"
            "fixture:appraisal-pattern:r8-b-j-w1-a1:combination-2"
        ),
        (
            "generated:appraisal-charm:rarity-7:"
            "fixture:appraisal-pattern:r7-a-j-a2:combination-1"
        ),
        (
            "generated:appraisal-charm:rarity-7:"
            "fixture:appraisal-pattern:r7-a-j-a2:combination-2"
        ),
    ]
    first_seen_generated_ids: list[str] = []
    all_charm_ids: set[str] = set()
    for candidate in result:
        charm = selected_charm(candidate)
        assert charm.part is EquipmentPart.CHARM
        all_charm_ids.add(charm.equipment_id)
        if (
            charm.equipment_id.startswith("generated:appraisal-charm:")
            and charm.equipment_id not in first_seen_generated_ids
        ):
            first_seen_generated_ids.append(charm.equipment_id)

    assert first_seen_generated_ids == expected_generated_ids
    assert set(first_seen_generated_ids) == set(expected_generated_ids)
    assert {
        "fixture:charm:power",
        "fixture:charm:precision",
    } <= all_charm_ids

    assert any(
        selected_charm(candidate).equipment_id.startswith("generated:appraisal-charm:")
        and {
            (
                placement.decoration_id,
                placement.slot_index,
            )
            for placement in candidate.placements
            if placement.equipment_id == selected_charm(candidate).equipment_id
        }
        >= {
            ("fixture:decoration:weapon-power-1", 0),
            ("fixture:decoration:armor-power-1", 1),
        }
        for candidate in result
    )


def test_attack_level_five_can_use_aggregated_attack_three_charm_route() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:attack-boost", 5),),
    )

    assert result
    generated_routes = [
        candidate
        for candidate in result
        if selected_charm(candidate).equipment_id.startswith(
            "generated:appraisal-charm:"
        )
        and selected_charm(candidate).skills
        and selected_charm(candidate).skills[0] == skill("skill:attack-boost", 3)
    ]
    assert generated_routes
    assert all(
        dict(candidate.skill_levels)["skill:attack-boost"] >= 5
        for candidate in generated_routes
    )


def test_weapon_technique_requirement_returns_generated_charm_routes() -> None:
    result = catalog_search(
        catalog=tiny_catalog(),
        requirements=(requirement("skill:fixture-weapon-technique", 1),),
    )

    assert result
    assert all(
        any(
            charm_skill.skill_id == "skill:fixture-weapon-technique"
            for charm_skill in selected_charm(candidate).skills
        )
        for candidate in result
    )
    assert all(
        selected_weapon(candidate).series_skill_id == "skill:fixture-series-bonus"
        and selected_weapon(candidate).group_skill_id == "skill:fixture-group-bonus"
        for candidate in result
    )


def test_weapon_technique_and_weakness_exploit_select_generated_routes() -> None:
    requirements = (
        requirement("skill:fixture-weapon-technique", 1),
        requirement("skill:weakness-exploit", 3),
    )

    result = catalog_search(catalog=tiny_catalog(), requirements=requirements)

    assert result
    assert all(
        {charm_skill.skill_id for charm_skill in selected_charm(candidate).skills}
        >= {
            "skill:fixture-weapon-technique",
            "skill:weakness-exploit",
        }
        for candidate in result
    )


def test_catalog_subclass_preserves_appraisal_generation() -> None:
    base = tiny_catalog()
    catalog = CatalogSubclass(
        schema_version=base.schema_version,
        equipment=base.equipment,
        decorations=base.decorations,
        skills=base.skills,
        appraisal_charm_skill_groups=base.appraisal_charm_skill_groups,
        appraisal_charm_patterns=base.appraisal_charm_patterns,
    )

    result = catalog_search(
        catalog=catalog,
        requirements=(requirement("skill:fixture-weapon-technique", 1),),
    )

    assert result
    assert all(
        selected_charm(candidate).equipment_id.startswith("generated:appraisal-charm:")
        for candidate in result
    )
