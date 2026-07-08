from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.solver import (
    BuildCandidate,
    SkillRequirement,
    enumerate_build_candidates,
    enumerate_decoration_placement_combinations,
    enumerate_equipment_selections,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.solver.filtering import (
    filter_build_candidates_by_skill_requirements,
)


def equipment_definition(
    equipment_id: str = "equipment:weapon",
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=EquipmentPart.WEAPON,
        skills=(),
        slots=(),
    )


def candidate(
    skill_levels: tuple[tuple[str, int], ...] = (("skill:attack-boost", 1),),
    equipment_id: str = "equipment:weapon",
) -> BuildCandidate:
    return BuildCandidate(
        equipment=(equipment_definition(equipment_id),),
        placements=(),
        skill_levels=skill_levels,
    )


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def candidate_generator() -> Iterator[BuildCandidate]:
    yield candidate()


def requirement_generator() -> Iterator[SkillRequirement]:
    yield requirement()


class CandidateTuple(tuple):
    pass


class RequirementTuple(tuple):
    pass


def filter_candidates(
    *,
    candidates: tuple[BuildCandidate, ...],
    requirements: tuple[SkillRequirement, ...],
) -> tuple[BuildCandidate, ...]:
    return filter_build_candidates_by_skill_requirements(
        candidates=candidates,
        requirements=requirements,
    )


def test_empty_candidates_returns_empty_tuple() -> None:
    assert filter_candidates(candidates=(), requirements=(requirement(),)) == ()


def test_empty_requirements_return_all_candidates() -> None:
    first = candidate(equipment_id="equipment:first")
    second = candidate(equipment_id="equipment:second")

    assert filter_candidates(candidates=(first, second), requirements=()) == (
        first,
        second,
    )


def test_single_candidate_is_returned_when_requirement_is_satisfied() -> None:
    build = candidate(skill_levels=(("skill:attack-boost", 2),))

    assert filter_candidates(
        candidates=(build,),
        requirements=(requirement("skill:attack-boost", 1),),
    ) == (build,)


def test_single_candidate_is_excluded_when_requirement_is_not_satisfied() -> None:
    build = candidate(skill_levels=(("skill:attack-boost", 1),))

    assert (
        filter_candidates(
            candidates=(build,),
            requirements=(requirement("skill:attack-boost", 2),),
        )
        == ()
    )


def test_returns_only_satisfying_candidates_from_multiple_candidates() -> None:
    first = candidate(
        skill_levels=(("skill:attack-boost", 2),),
        equipment_id="equipment:first",
    )
    second = candidate(
        skill_levels=(("skill:attack-boost", 1),),
        equipment_id="equipment:second",
    )
    third = candidate(
        skill_levels=(("skill:attack-boost", 3),),
        equipment_id="equipment:third",
    )

    assert filter_candidates(
        candidates=(first, second, third),
        requirements=(requirement("skill:attack-boost", 2),),
    ) == (first, third)


def test_candidate_must_satisfy_all_requirements() -> None:
    build = candidate(
        skill_levels=(
            ("skill:attack-boost", 2),
            ("skill:critical-eye", 1),
        ),
    )

    assert filter_candidates(
        candidates=(build,),
        requirements=(
            requirement("skill:attack-boost", 2),
            requirement("skill:critical-eye", 1),
        ),
    ) == (build,)


def test_candidate_is_excluded_when_any_requirement_is_not_satisfied() -> None:
    build = candidate(
        skill_levels=(
            ("skill:attack-boost", 2),
            ("skill:critical-eye", 1),
        ),
    )

    assert (
        filter_candidates(
            candidates=(build,),
            requirements=(
                requirement("skill:attack-boost", 2),
                requirement("skill:critical-eye", 2),
            ),
        )
        == ()
    )


def test_missing_skill_is_treated_as_zero() -> None:
    build = candidate(skill_levels=(("skill:attack-boost", 2),))

    assert (
        filter_candidates(
            candidates=(build,),
            requirements=(requirement("skill:critical-eye", 1),),
        )
        == ()
    )


def test_exact_level_satisfies_requirement() -> None:
    build = candidate(skill_levels=(("skill:attack-boost", 2),))

    assert filter_candidates(
        candidates=(build,),
        requirements=(requirement("skill:attack-boost", 2),),
    ) == (build,)


def test_greater_level_satisfies_requirement() -> None:
    build = candidate(skill_levels=(("skill:attack-boost", 3),))

    assert filter_candidates(
        candidates=(build,),
        requirements=(requirement("skill:attack-boost", 2),),
    ) == (build,)


def test_extra_skill_levels_are_ignored() -> None:
    build = candidate(
        skill_levels=(
            ("skill:attack-boost", 1),
            ("skill:unused", 999),
        ),
    )

    assert filter_candidates(
        candidates=(build,),
        requirements=(requirement("skill:attack-boost", 1),),
    ) == (build,)


def test_skill_id_text_is_not_normalized() -> None:
    build = candidate(skill_levels=(("Skill:Internal_ID-01", 1),))

    assert filter_candidates(
        candidates=(build,),
        requirements=(requirement("Skill:Internal_ID-01", 1),),
    ) == (build,)
    assert (
        filter_candidates(
            candidates=(build,),
            requirements=(requirement("skill:internal_id-01", 1),),
        )
        == ()
    )


def test_result_preserves_input_candidate_order() -> None:
    first = candidate(equipment_id="equipment:first")
    second = candidate(equipment_id="equipment:second")
    third = candidate(equipment_id="equipment:third")

    assert filter_candidates(
        candidates=(first, second, third),
        requirements=(requirement(),),
    ) == (first, second, third)


def test_return_value_is_tuple() -> None:
    result = filter_candidates(candidates=(candidate(),), requirements=(requirement(),))

    assert type(result) is tuple


def test_arguments_are_keyword_only() -> None:
    signature = inspect.signature(filter_build_candidates_by_skill_requirements)

    assert signature.parameters["candidates"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["requirements"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        filter_build_candidates_by_skill_requirements((), ())  # type: ignore[call-arg]


def test_inputs_are_not_modified() -> None:
    candidates = (candidate(),)
    requirements = (requirement(),)
    original_candidates = candidates
    original_requirements = requirements

    result = filter_candidates(candidates=candidates, requirements=requirements)

    assert candidates == original_candidates
    assert requirements == original_requirements
    assert result[0] is candidates[0]


def test_solver_package_exports_filter_function() -> None:
    from mhwilds_skill_sim.solver import (
        filter_build_candidates_by_skill_requirements as exported_function,
    )

    assert exported_function is filter_build_candidates_by_skill_requirements


def test_solver_package_keeps_existing_public_exports() -> None:
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
        skill_levels_satisfy_requirements as exported_requirements,
    )

    assert ExportedBuildCandidate is BuildCandidate
    assert ExportedRequirement is SkillRequirement
    assert exported_builds is enumerate_build_candidates
    assert exported_decorations is enumerate_decoration_placement_combinations
    assert exported_equipment is enumerate_equipment_selections
    assert exported_requirements is skill_levels_satisfy_requirements


@pytest.mark.parametrize(
    "candidates", [[candidate()], {candidate()}, candidate_generator(), None]
)
def test_rejects_non_tuple_candidates(candidates: object) -> None:
    with pytest.raises(TypeError, match="candidates"):
        filter_build_candidates_by_skill_requirements(
            candidates=candidates,  # type: ignore[arg-type]
            requirements=(),
        )


def test_rejects_candidates_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="candidates"):
        filter_build_candidates_by_skill_requirements(
            candidates=CandidateTuple((candidate(),)),
            requirements=(),
        )


@pytest.mark.parametrize(
    "requirements",
    [[requirement()], {requirement()}, requirement_generator(), None],
)
def test_rejects_non_tuple_requirements(requirements: object) -> None:
    with pytest.raises(TypeError, match="requirements"):
        filter_build_candidates_by_skill_requirements(
            candidates=(),
            requirements=requirements,  # type: ignore[arg-type]
        )


def test_rejects_requirements_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="requirements"):
        filter_build_candidates_by_skill_requirements(
            candidates=(),
            requirements=RequirementTuple((requirement(),)),
        )


@pytest.mark.parametrize("invalid_candidate", ["candidate", None])
def test_rejects_invalid_candidate_elements(invalid_candidate: object) -> None:
    with pytest.raises(TypeError, match="candidates"):
        filter_build_candidates_by_skill_requirements(
            candidates=(invalid_candidate,),  # type: ignore[arg-type]
            requirements=(),
        )


@pytest.mark.parametrize("invalid_requirement", ["skill:attack-boost", None])
def test_rejects_invalid_requirement_elements(invalid_requirement: object) -> None:
    with pytest.raises(TypeError, match="requirements"):
        filter_build_candidates_by_skill_requirements(
            candidates=(),
            requirements=(invalid_requirement,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_requirement_skill_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        filter_build_candidates_by_skill_requirements(
            candidates=(),
            requirements=(
                requirement("skill:attack-boost", 1),
                requirement("skill:attack-boost", 2),
            ),
        )


def test_filters_already_built_candidates_without_reenumeration() -> None:
    unsatisfied = candidate(
        skill_levels=(("skill:attack-boost", 1),),
        equipment_id="equipment:unsatisfied",
    )
    satisfied = candidate(
        skill_levels=(("skill:attack-boost", 2),),
        equipment_id="equipment:satisfied",
    )

    assert filter_candidates(
        candidates=(unsatisfied, satisfied),
        requirements=(requirement("skill:attack-boost", 2),),
    ) == (satisfied,)


def test_filtering_does_not_mutate_candidate_contents() -> None:
    build = candidate(skill_levels=(("skill:attack-boost", 1),))
    before = build

    filter_candidates(candidates=(build,), requirements=(requirement(),))

    assert build == before
