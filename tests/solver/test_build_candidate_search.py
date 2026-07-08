from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
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
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=slots,
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
) -> tuple[EquipmentDefinition, ...]:
    return (
        equipment_definition(
            EquipmentPart.WEAPON,
            weapon_id,
            skills=weapon_skills,
            slots=weapon_slots,
        ),
        equipment_definition(EquipmentPart.HEAD, head_id, skills=head_skills),
        equipment_definition(
            EquipmentPart.CHEST,
            "equipment:chest",
            skills=chest_skills,
        ),
        equipment_definition(EquipmentPart.ARMS, "equipment:arms", skills=arms_skills),
        equipment_definition(
            EquipmentPart.WAIST,
            "equipment:waist",
            skills=waist_skills,
        ),
        equipment_definition(EquipmentPart.LEGS, "equipment:legs", skills=legs_skills),
        equipment_definition(EquipmentPart.CHARM, charm_id, skills=charm_skills),
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
) -> tuple[BuildCandidate, ...]:
    return search_build_candidates_by_skill_requirements(
        equipment=equipment,
        decorations=decorations,
        requirements=requirements,
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

    with pytest.raises(TypeError):
        search_build_candidates_by_skill_requirements(complete_equipment(), (), ())  # type: ignore[call-arg]


def test_inputs_are_not_modified() -> None:
    equipment = complete_equipment(weapon_slots=(weapon_slot(1),))
    decorations = (decoration_definition(),)
    requirements = (requirement("skill:decoration-default", 1),)
    original_equipment = equipment
    original_decorations = decorations
    original_requirements = requirements

    search_candidates(
        equipment=equipment,
        decorations=decorations,
        requirements=requirements,
    )

    assert equipment == original_equipment
    assert decorations == original_decorations
    assert requirements == original_requirements


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
