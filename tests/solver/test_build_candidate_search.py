from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
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
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.solver.search import (
    search_build_candidates_by_skill_requirements,
)
from mhwilds_skill_sim.validation.placement import DecorationPlacement


REQUIRED_PARTS = (
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
)


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
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
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
    )


def complete_equipment(
    *,
    weapon_id: str = "equipment:weapon",
    head_id: str = "equipment:head",
    charm_id: str = "equipment:charm",
    weapon_skills: tuple[SkillContribution, ...] = (),
    head_skills: tuple[SkillContribution, ...] = (),
    chest_skills: tuple[SkillContribution, ...] = (),
    arms_skills: tuple[SkillContribution, ...] = (),
    waist_skills: tuple[SkillContribution, ...] = (),
    legs_skills: tuple[SkillContribution, ...] = (),
    charm_skills: tuple[SkillContribution, ...] = (),
    weapon_slots: tuple[DecorationSlot, ...] = (),
    series_parts: tuple[EquipmentPart, ...] = (),
    group_parts: tuple[EquipmentPart, ...] = (),
    series_skill_id: str = "skill:series-bonus",
    group_skill_id: str = "skill:group-bonus",
    weapon_allows_series_skill_assignment: bool = False,
    weapon_allows_group_skill_assignment: bool = False,
) -> tuple[EquipmentDefinition, ...]:
    equipment_ids = {
        EquipmentPart.WEAPON: weapon_id,
        EquipmentPart.HEAD: head_id,
        EquipmentPart.CHEST: "equipment:chest",
        EquipmentPart.ARMS: "equipment:arms",
        EquipmentPart.WAIST: "equipment:waist",
        EquipmentPart.LEGS: "equipment:legs",
        EquipmentPart.CHARM: charm_id,
    }
    skills_by_part = {
        EquipmentPart.WEAPON: weapon_skills,
        EquipmentPart.HEAD: head_skills,
        EquipmentPart.CHEST: chest_skills,
        EquipmentPart.ARMS: arms_skills,
        EquipmentPart.WAIST: waist_skills,
        EquipmentPart.LEGS: legs_skills,
        EquipmentPart.CHARM: charm_skills,
    }
    return tuple(
        equipment_definition(
            part,
            equipment_ids[part],
            skills=skills_by_part[part],
            slots=weapon_slots if part is EquipmentPart.WEAPON else (),
            series_skill_id=series_skill_id if part in series_parts else None,
            group_skill_id=group_skill_id if part in group_parts else None,
            allows_series_skill_assignment=(
                weapon_allows_series_skill_assignment
                if part is EquipmentPart.WEAPON
                else False
            ),
            allows_group_skill_assignment=(
                weapon_allows_group_skill_assignment
                if part is EquipmentPart.WEAPON
                else False
            ),
        )
        for part in REQUIRED_PARTS
    )


def bonus_skill_definition(
    skill_id: str,
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


def series_skill_definition(
    skill_id: str = "skill:series-bonus",
    thresholds: tuple[int, ...] = (2, 4),
) -> SkillDefinition:
    return bonus_skill_definition(skill_id, SkillKind.SERIES, thresholds)


def group_skill_definition(
    skill_id: str = "skill:group-bonus",
    thresholds: tuple[int, ...] = (3,),
) -> SkillDefinition:
    return bonus_skill_definition(skill_id, SkillKind.GROUP, thresholds)


def normal_skill_definition(
    skill_id: str = "skill:attack-boost",
    *,
    kind: SkillKind = SkillKind.ARMOR,
    maximum_level: int = 3,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=tuple(
            SkillRankDefinition(level=level, required_pieces=None)
            for level in range(1, maximum_level + 1)
        ),
    )


def appraisal_skill_group(
    group_id: str = "appraisal-group:A",
    skills: tuple[SkillContribution, ...] = (
        SkillContribution("skill:attack-boost", 1),
    ),
) -> AppraisalCharmSkillGroupDefinition:
    return AppraisalCharmSkillGroupDefinition(group_id=group_id, skills=skills)


def appraisal_pattern(
    pattern_id: str = "appraisal-pattern:r8-a",
    *,
    skill_group_ids: tuple[str, ...] = ("appraisal-group:A",),
) -> AppraisalCharmPatternDefinition:
    return AppraisalCharmPatternDefinition(
        pattern_id=pattern_id,
        rarity=8,
        skill_group_ids=skill_group_ids,
        slots=(),
    )


def artian_skill_definitions() -> tuple[SkillDefinition, ...]:
    return (
        series_skill_definition("skill:series-a", (1,)),
        series_skill_definition("skill:series-b", (1,)),
        group_skill_definition("skill:group-a", (1,)),
        group_skill_definition("skill:group-b", (1,)),
    )


def artian_equipment() -> tuple[EquipmentDefinition, ...]:
    return complete_equipment(
        weapon_allows_series_skill_assignment=True,
        weapon_allows_group_skill_assignment=True,
    )


def two_head_equipment(
    *,
    head_a_skills: tuple[SkillContribution, ...] = (),
    head_b_skills: tuple[SkillContribution, ...] = (),
    weapon_slots: tuple[DecorationSlot, ...] = (),
) -> tuple[EquipmentDefinition, ...]:
    return (
        equipment_definition(
            EquipmentPart.WEAPON,
            "equipment:weapon",
            slots=weapon_slots,
        ),
        equipment_definition(
            EquipmentPart.HEAD,
            "equipment:head-a",
            skills=head_a_skills,
        ),
        equipment_definition(
            EquipmentPart.HEAD,
            "equipment:head-b",
            skills=head_b_skills,
        ),
        *(
            equipment_definition(part, f"equipment:{part.value}")
            for part in REQUIRED_PARTS
            if part not in {EquipmentPart.WEAPON, EquipmentPart.HEAD}
        ),
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


def placement(
    equipment_id: str = "equipment:weapon",
    slot_index: int = 0,
    decoration_id: str = "decoration:weapon-1",
) -> DecorationPlacement:
    return DecorationPlacement(
        equipment_id=equipment_id,
        slot_index=slot_index,
        decoration_id=decoration_id,
    )


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def search_candidates(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    decorations: tuple[DecorationDefinition, ...],
    requirements: tuple[SkillRequirement, ...],
    skill_definitions: tuple[SkillDefinition, ...] = (),
    appraisal_charm_skill_groups: tuple[AppraisalCharmSkillGroupDefinition, ...] = (),
    appraisal_charm_patterns: tuple[AppraisalCharmPatternDefinition, ...] = (),
) -> tuple[BuildCandidate, ...]:
    return search_build_candidates_by_skill_requirements(
        equipment=equipment,
        decorations=decorations,
        requirements=requirements,
        skill_definitions=skill_definitions,
        appraisal_charm_skill_groups=appraisal_charm_skill_groups,
        appraisal_charm_patterns=appraisal_charm_patterns,
    )


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition(EquipmentPart.WEAPON)


def decoration_generator() -> Iterator[DecorationDefinition]:
    yield decoration_definition()


def requirement_generator() -> Iterator[SkillRequirement]:
    yield requirement()


def candidate_equipment_ids(
    candidates: tuple[BuildCandidate, ...],
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(definition.equipment_id for definition in build.equipment)
        for build in candidates
    )


def test_empty_requirements_return_all_enumerated_candidates() -> None:
    equipment = complete_equipment(weapon_slots=(weapon_slot(1),))
    decorations = (decoration_definition(),)

    result = search_candidates(
        equipment=equipment,
        decorations=decorations,
        requirements=(),
    )

    assert tuple(build.placements for build in result) == (
        (),
        (placement(),),
    )


def test_satisfied_requirement_returns_candidate() -> None:
    equipment = complete_equipment(weapon_skills=(skill("skill:attack-boost", 2),))

    result = search_candidates(
        equipment=equipment,
        decorations=(),
        requirements=(requirement("skill:attack-boost", 2),),
    )

    assert len(result) == 1
    assert result[0].equipment == equipment


def test_unsatisfied_requirement_returns_empty_tuple() -> None:
    result = search_candidates(
        equipment=complete_equipment(weapon_skills=(skill("skill:attack-boost", 1),)),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 2),),
    )

    assert result == ()


def test_equipment_skills_alone_can_satisfy_requirements() -> None:
    equipment = complete_equipment(head_skills=(skill("skill:critical-eye", 3),))

    result = search_candidates(
        equipment=equipment,
        decorations=(),
        requirements=(requirement("skill:critical-eye", 3),),
    )

    assert candidate_equipment_ids(result) == (
        tuple(definition.equipment_id for definition in equipment),
    )


def test_direct_search_can_satisfy_series_skill_requirement() -> None:
    result = search_candidates(
        equipment=complete_equipment(
            series_parts=(EquipmentPart.HEAD, EquipmentPart.CHEST),
        ),
        decorations=(),
        requirements=(requirement("skill:series-bonus", 1),),
        skill_definitions=(series_skill_definition(),),
    )

    assert len(result) == 1
    assert dict(result[0].skill_levels)["skill:series-bonus"] == 1


def test_direct_search_can_satisfy_group_skill_requirement() -> None:
    result = search_candidates(
        equipment=complete_equipment(
            group_parts=(
                EquipmentPart.HEAD,
                EquipmentPart.CHEST,
                EquipmentPart.ARMS,
            ),
        ),
        decorations=(),
        requirements=(requirement("skill:group-bonus", 1),),
        skill_definitions=(group_skill_definition(),),
    )

    assert len(result) == 1
    assert dict(result[0].skill_levels)["skill:group-bonus"] == 1


def test_series_requirement_selects_generated_series_variants() -> None:
    result = search_candidates(
        equipment=artian_equipment(),
        decorations=(),
        requirements=(requirement("skill:series-b", 1),),
        skill_definitions=artian_skill_definitions(),
    )

    assert [
        (candidate.equipment[0].series_skill_id, candidate.equipment[0].group_skill_id)
        for candidate in result
    ] == [
        ("skill:series-b", "skill:group-a"),
        ("skill:series-b", "skill:group-b"),
    ]


def test_group_requirement_selects_generated_group_variants() -> None:
    result = search_candidates(
        equipment=artian_equipment(),
        decorations=(),
        requirements=(requirement("skill:group-b", 1),),
        skill_definitions=artian_skill_definitions(),
    )

    assert [
        (candidate.equipment[0].series_skill_id, candidate.equipment[0].group_skill_id)
        for candidate in result
    ] == [
        ("skill:series-a", "skill:group-b"),
        ("skill:series-b", "skill:group-b"),
    ]


def test_simultaneous_requirements_select_generated_combination() -> None:
    result = search_candidates(
        equipment=artian_equipment(),
        decorations=(),
        requirements=(
            requirement("skill:series-b", 1),
            requirement("skill:group-a", 1),
        ),
        skill_definitions=artian_skill_definitions(),
    )

    assert len(result) == 1
    assert result[0].equipment[0].series_skill_id == "skill:series-b"
    assert result[0].equipment[0].group_skill_id == "skill:group-a"


def test_generated_variant_search_order_is_deterministic() -> None:
    result = search_candidates(
        equipment=artian_equipment(),
        decorations=(),
        requirements=(),
        skill_definitions=artian_skill_definitions(),
    )

    assert [
        (candidate.equipment[0].series_skill_id, candidate.equipment[0].group_skill_id)
        for candidate in result
    ] == [
        ("skill:series-a", "skill:group-a"),
        ("skill:series-a", "skill:group-b"),
        ("skill:series-b", "skill:group-a"),
        ("skill:series-b", "skill:group-b"),
    ]


def test_nonmatching_generated_variant_requirement_returns_empty() -> None:
    result = search_candidates(
        equipment=artian_equipment(),
        decorations=(),
        requirements=(requirement("skill:series-missing", 1),),
        skill_definitions=artian_skill_definitions(),
    )

    assert result == ()


def test_omitting_skill_definitions_preserves_legacy_no_membership_search() -> None:
    equipment = complete_equipment(
        weapon_skills=(skill("skill:attack-boost", 1),),
    )
    requirements = (requirement("skill:attack-boost", 1),)

    assert search_candidates(
        equipment=equipment,
        decorations=(),
        requirements=requirements,
    ) == search_candidates(
        equipment=equipment,
        decorations=(),
        requirements=requirements,
        skill_definitions=(),
    )


def test_skill_definitions_are_passed_through_to_enumeration() -> None:
    equipment = complete_equipment(series_parts=(EquipmentPart.HEAD,))

    with pytest.raises(ValueError, match="series_skill_id"):
        search_candidates(
            equipment=equipment,
            decorations=(),
            requirements=(),
        )


def test_decoration_skills_can_satisfy_requirements() -> None:
    result = search_candidates(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(decoration_definition(skills=(skill("skill:critical-eye", 1),)),),
        requirements=(requirement("skill:critical-eye", 1),),
    )

    assert tuple(build.placements for build in result) == ((placement(),),)


def test_unsatisfied_empty_placement_candidate_is_excluded_when_decoration_satisfies() -> (
    None
):
    result = search_candidates(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(
            decoration_definition(skills=(skill("skill:weakness-exploit", 1),)),
        ),
        requirements=(requirement("skill:weakness-exploit", 1),),
    )

    assert len(result) == 1
    assert result[0].placements == (placement(),)


def test_only_satisfying_head_candidate_is_returned() -> None:
    result = search_candidates(
        equipment=two_head_equipment(
            head_a_skills=(skill("skill:attack-boost", 1),),
            head_b_skills=(skill("skill:attack-boost", 2),),
        ),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 2),),
    )

    assert tuple(build.equipment[1].equipment_id for build in result) == (
        "equipment:head-b",
    )


def test_multiple_requirements_must_all_be_satisfied() -> None:
    result = search_candidates(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 2),),
            head_skills=(skill("skill:critical-eye", 1),),
        ),
        decorations=(),
        requirements=(
            requirement("skill:attack-boost", 2),
            requirement("skill:critical-eye", 1),
        ),
    )

    assert len(result) == 1


def test_missing_skill_is_treated_as_zero_and_excluded() -> None:
    result = search_candidates(
        equipment=complete_equipment(weapon_skills=(skill("skill:attack-boost", 2),)),
        decorations=(),
        requirements=(requirement("skill:critical-eye", 1),),
    )

    assert result == ()


def test_extra_skill_levels_are_ignored() -> None:
    result = search_candidates(
        equipment=complete_equipment(
            weapon_skills=(
                skill("skill:attack-boost", 1),
                skill("skill:unused", 999),
            ),
        ),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 1),),
    )

    assert len(result) == 1


def test_skill_id_text_is_not_normalized() -> None:
    equipment = complete_equipment(weapon_skills=(skill("Skill:Internal_ID-01", 1),))

    assert (
        len(
            search_candidates(
                equipment=equipment,
                decorations=(),
                requirements=(requirement("Skill:Internal_ID-01", 1),),
            )
        )
        == 1
    )
    assert (
        search_candidates(
            equipment=equipment,
            decorations=(),
            requirements=(requirement("skill:internal_id-01", 1),),
        )
        == ()
    )


def test_result_preserves_enumeration_order_after_filtering() -> None:
    result = search_candidates(
        equipment=two_head_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(decoration_definition(),),
        requirements=(requirement("skill:decoration-default", 1),),
    )

    assert [
        (build.equipment[1].equipment_id, build.placements) for build in result
    ] == [
        ("equipment:head-a", (placement(),)),
        ("equipment:head-b", (placement(),)),
    ]


def test_result_order_is_unchanged_when_skill_definitions_are_supplied() -> None:
    equipment = two_head_equipment(weapon_slots=(weapon_slot(1),))
    decorations = (decoration_definition(),)
    requirements = (requirement("skill:decoration-default", 1),)

    legacy = search_candidates(
        equipment=equipment,
        decorations=decorations,
        requirements=requirements,
    )
    with_definitions = search_candidates(
        equipment=equipment,
        decorations=decorations,
        requirements=requirements,
        skill_definitions=(series_skill_definition(), group_skill_definition()),
    )

    assert with_definitions == legacy


def test_returns_tuple_with_build_candidate_elements() -> None:
    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(),
    )

    assert type(result) is tuple
    assert all(isinstance(build, BuildCandidate) for build in result)


def test_search_requires_keyword_arguments() -> None:
    signature = inspect.signature(search_build_candidates_by_skill_requirements)

    assert signature.parameters["equipment"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["decorations"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["requirements"].kind is inspect.Parameter.KEYWORD_ONLY
    assert (
        signature.parameters["skill_definitions"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    assert signature.parameters["skill_definitions"].default == ()

    with pytest.raises(TypeError):
        search_build_candidates_by_skill_requirements(complete_equipment(), (), ())  # type: ignore[call-arg]


def test_inputs_are_not_modified() -> None:
    equipment = complete_equipment(weapon_slots=(weapon_slot(1),))
    decorations = (decoration_definition(),)
    requirements = (requirement("skill:decoration-default", 1),)
    skill_definitions = (series_skill_definition(),)
    original_equipment = equipment
    original_decorations = decorations
    original_requirements = requirements
    original_skill_definitions = skill_definitions

    search_candidates(
        equipment=equipment,
        decorations=decorations,
        requirements=requirements,
        skill_definitions=skill_definitions,
    )

    assert equipment == original_equipment
    assert decorations == original_decorations
    assert requirements == original_requirements
    assert skill_definitions == original_skill_definitions


def test_solver_package_exports_search_and_keeps_existing_public_exports() -> None:
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
        skill_levels_satisfy_requirements as exported_requirements,
    )

    assert ExportedBuildCandidate is BuildCandidate
    assert ExportedRequirement is SkillRequirement
    assert exported_builds is enumerate_build_candidates
    assert exported_decorations is enumerate_decoration_placement_combinations
    assert exported_equipment is enumerate_equipment_selections
    assert exported_filter is filter_build_candidates_by_skill_requirements
    assert exported_search is search_build_candidates_by_skill_requirements
    assert exported_requirements is skill_levels_satisfy_requirements


@pytest.mark.parametrize(
    "equipment",
    [
        (),
        tuple(
            equipment_definition(part)
            for part in REQUIRED_PARTS
            if part is not EquipmentPart.WEAPON
        ),
        tuple(
            equipment_definition(part)
            for part in REQUIRED_PARTS
            if part is not EquipmentPart.CHARM
        ),
    ],
)
def test_empty_or_missing_equipment_cases_return_empty_tuple(
    equipment: tuple[EquipmentDefinition, ...],
) -> None:
    assert (
        search_candidates(
            equipment=equipment,
            decorations=(),
            requirements=(requirement(),),
        )
        == ()
    )


def test_empty_decorations_with_satisfying_equipment_skills_return_candidate() -> None:
    result = search_candidates(
        equipment=complete_equipment(weapon_skills=(skill("skill:attack-boost", 1),)),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 1),),
    )

    assert len(result) == 1


def test_empty_decorations_with_unsatisfied_requirements_return_empty_tuple() -> None:
    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 1),),
    )

    assert result == ()


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_definition(EquipmentPart.WEAPON)],
        equipment_generator(),
    ],
)
def test_propagates_equipment_type_errors(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        search_build_candidates_by_skill_requirements(
            equipment=equipment,  # type: ignore[arg-type]
            decorations=(),
            requirements=(),
        )


def test_propagates_decoration_list_type_error() -> None:
    with pytest.raises(TypeError, match="decorations"):
        search_build_candidates_by_skill_requirements(
            equipment=complete_equipment(),
            decorations=[decoration_definition()],  # type: ignore[arg-type]
            requirements=(),
        )


def test_propagates_requirement_list_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_build_candidates_by_skill_requirements(
            equipment=complete_equipment(),
            decorations=(),
            requirements=[requirement()],  # type: ignore[arg-type]
        )


def test_propagates_invalid_equipment_element_type_error() -> None:
    with pytest.raises(TypeError, match="equipment"):
        search_build_candidates_by_skill_requirements(
            equipment=("equipment:weapon",),  # type: ignore[arg-type]
            decorations=(),
            requirements=(),
        )


def test_propagates_invalid_decoration_element_type_error() -> None:
    with pytest.raises(TypeError, match="decorations"):
        search_build_candidates_by_skill_requirements(
            equipment=complete_equipment(),
            decorations=("decoration:weapon-1",),  # type: ignore[arg-type]
            requirements=(),
        )


def test_propagates_invalid_requirement_element_type_error() -> None:
    with pytest.raises(TypeError, match="requirements"):
        search_build_candidates_by_skill_requirements(
            equipment=complete_equipment(),
            decorations=(),
            requirements=("skill:attack-boost",),  # type: ignore[arg-type]
        )


def test_propagates_duplicate_equipment_id_value_error() -> None:
    equipment = (
        equipment_definition(EquipmentPart.WEAPON, "equipment:duplicate"),
        equipment_definition(EquipmentPart.HEAD, "equipment:duplicate"),
        *(
            equipment_definition(part, f"equipment:{part.value}")
            for part in REQUIRED_PARTS
            if part not in {EquipmentPart.WEAPON, EquipmentPart.HEAD}
        ),
    )

    with pytest.raises(ValueError, match="equipment"):
        search_build_candidates_by_skill_requirements(
            equipment=equipment,
            decorations=(),
            requirements=(),
        )


def test_propagates_duplicate_decoration_id_value_error() -> None:
    with pytest.raises(ValueError, match="decorations"):
        search_build_candidates_by_skill_requirements(
            equipment=complete_equipment(),
            decorations=(
                decoration_definition("decoration:duplicate"),
                decoration_definition("decoration:duplicate"),
            ),
            requirements=(),
        )


def test_propagates_duplicate_requirement_skill_id_value_error() -> None:
    with pytest.raises(ValueError, match="requirements"):
        search_build_candidates_by_skill_requirements(
            equipment=complete_equipment(),
            decorations=(),
            requirements=(
                requirement("skill:attack-boost", 1),
                requirement("skill:attack-boost", 2),
            ),
        )


def test_search_does_not_rank_or_limit_satisfying_candidates() -> None:
    result = search_candidates(
        equipment=two_head_equipment(
            head_a_skills=(skill("skill:attack-boost", 2),),
            head_b_skills=(skill("skill:attack-boost", 99),),
        ),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 1),),
    )

    assert tuple(build.equipment[1].equipment_id for build in result) == (
        "equipment:head-a",
        "equipment:head-b",
    )


def test_search_adds_no_request_or_result_public_types() -> None:
    import mhwilds_skill_sim.solver as solver
    import mhwilds_skill_sim.solver.search as search_module

    for name in ("SearchRequest", "SolverResult", "BuildResult"):
        assert not hasattr(solver, name)
        assert not hasattr(search_module, name)


def test_public_search_can_be_used_without_direct_filter_dependency() -> None:
    from mhwilds_skill_sim.solver import (
        search_build_candidates_by_skill_requirements as public_search,
    )

    result = public_search(
        equipment=complete_equipment(weapon_skills=(skill("skill:attack-boost", 1),)),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 1),),
    )

    assert len(result) == 1


def test_generated_charm_satisfies_armor_skill_requirement() -> None:
    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 2),),
        skill_definitions=(normal_skill_definition(maximum_level=2),),
        appraisal_charm_skill_groups=(
            appraisal_skill_group(skills=(skill("skill:attack-boost", 2),)),
        ),
        appraisal_charm_patterns=(appraisal_pattern(),),
    )

    assert len(result) == 1
    assert result[0].equipment[-1].equipment_id.startswith("generated:appraisal-charm:")
    assert result[0].equipment[-1].skills == (skill("skill:attack-boost", 2),)


def test_generated_charm_satisfies_weapon_skill_requirement() -> None:
    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(requirement("skill:weapon-technique", 1),),
        skill_definitions=(
            normal_skill_definition(
                "skill:weapon-technique",
                kind=SkillKind.WEAPON,
                maximum_level=1,
            ),
        ),
        appraisal_charm_skill_groups=(
            appraisal_skill_group(
                skills=(skill("skill:weapon-technique", 1),),
            ),
        ),
        appraisal_charm_patterns=(appraisal_pattern(),),
    )

    assert len(result) == 1
    assert dict(result[0].skill_levels)["skill:weapon-technique"] == 1


def test_summed_duplicate_charm_skills_satisfy_higher_requirement() -> None:
    groups = (
        appraisal_skill_group(
            "appraisal-group:B",
            (skill("skill:attack-boost", 2),),
        ),
        appraisal_skill_group(
            "appraisal-group:A",
            (skill("skill:attack-boost", 1),),
        ),
    )

    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(requirement("skill:attack-boost", 3),),
        skill_definitions=(normal_skill_definition(maximum_level=3),),
        appraisal_charm_skill_groups=groups,
        appraisal_charm_patterns=(
            appraisal_pattern(
                skill_group_ids=("appraisal-group:B", "appraisal-group:A"),
            ),
        ),
    )

    assert len(result) == 1
    assert result[0].equipment[-1].skills == (skill("skill:attack-boost", 3),)


def test_simultaneous_requirements_select_correct_generated_charm() -> None:
    groups = (
        appraisal_skill_group(
            "appraisal-group:B",
            (
                skill("skill:attack-boost", 2),
                skill("skill:weapon-technique", 1),
            ),
        ),
        appraisal_skill_group(
            "appraisal-group:J",
            (skill("skill:weakness-exploit", 1),),
        ),
    )

    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(
            requirement("skill:weapon-technique", 1),
            requirement("skill:weakness-exploit", 1),
        ),
        skill_definitions=(
            normal_skill_definition("skill:attack-boost"),
            normal_skill_definition(
                "skill:weapon-technique",
                kind=SkillKind.WEAPON,
                maximum_level=1,
            ),
            normal_skill_definition("skill:weakness-exploit"),
        ),
        appraisal_charm_skill_groups=groups,
        appraisal_charm_patterns=(
            appraisal_pattern(
                skill_group_ids=("appraisal-group:B", "appraisal-group:J"),
            ),
        ),
    )

    assert len(result) == 1
    assert result[0].equipment[-1].skills == (
        skill("skill:weapon-technique", 1),
        skill("skill:weakness-exploit", 1),
    )
    assert result[0].equipment[-1].equipment_id.endswith("combination-2")


def test_requirement_absent_from_generated_charms_returns_empty() -> None:
    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(requirement("skill:not-generated", 1),),
        skill_definitions=(normal_skill_definition(),),
        appraisal_charm_skill_groups=(appraisal_skill_group(),),
        appraisal_charm_patterns=(appraisal_pattern(),),
    )

    assert result == ()


def test_direct_search_result_order_follows_generated_charm_order() -> None:
    groups = (
        appraisal_skill_group(
            "appraisal-group:A",
            (
                skill("skill:attack-boost", 1),
                skill("skill:critical-eye", 1),
            ),
        ),
        appraisal_skill_group(
            "appraisal-group:J",
            (skill("skill:weakness-exploit", 1),),
        ),
    )

    result = search_candidates(
        equipment=complete_equipment(),
        decorations=(),
        requirements=(requirement("skill:weakness-exploit", 1),),
        skill_definitions=(
            normal_skill_definition("skill:attack-boost"),
            normal_skill_definition("skill:critical-eye"),
            normal_skill_definition("skill:weakness-exploit"),
        ),
        appraisal_charm_skill_groups=groups,
        appraisal_charm_patterns=(
            appraisal_pattern(
                skill_group_ids=("appraisal-group:A", "appraisal-group:J"),
            ),
        ),
    )

    assert [candidate.equipment[-1].skills for candidate in result] == [
        (
            skill("skill:attack-boost", 1),
            skill("skill:weakness-exploit", 1),
        ),
        (
            skill("skill:critical-eye", 1),
            skill("skill:weakness-exploit", 1),
        ),
    ]


def test_search_appraisal_arguments_are_keyword_only_and_default_empty() -> None:
    signature = inspect.signature(search_build_candidates_by_skill_requirements)

    for field_name in (
        "appraisal_charm_skill_groups",
        "appraisal_charm_patterns",
    ):
        assert signature.parameters[field_name].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters[field_name].default == ()


def test_omitting_appraisal_arguments_preserves_legacy_search() -> None:
    equipment = complete_equipment(
        weapon_skills=(skill("skill:attack-boost", 1),),
    )
    requirements = (requirement("skill:attack-boost", 1),)

    legacy = search_candidates(
        equipment=equipment,
        decorations=(),
        requirements=requirements,
    )
    explicit_empty = search_candidates(
        equipment=equipment,
        decorations=(),
        requirements=requirements,
        appraisal_charm_skill_groups=(),
        appraisal_charm_patterns=(),
    )

    assert explicit_empty == legacy
