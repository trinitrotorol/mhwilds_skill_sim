from __future__ import annotations

import inspect
from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.solver import (
    enumerate_decoration_placement_combinations,
    enumerate_equipment_selections,
)
from mhwilds_skill_sim.solver.requirements import (
    SkillRequirement,
    skill_levels_satisfy_requirements,
)


def requirement(
    skill_id: str = "skill:attack-boost",
    min_level: int = 1,
) -> SkillRequirement:
    return SkillRequirement(skill_id=skill_id, min_level=min_level)


def requirement_generator() -> Iterator[SkillRequirement]:
    yield requirement()


class SkillLevelDict(dict[str, int]):
    pass


class RequirementTuple(tuple):
    pass


def test_skill_requirement_keeps_valid_values() -> None:
    value = SkillRequirement(skill_id="skill:attack-boost", min_level=2)

    assert value.skill_id == "skill:attack-boost"
    assert value.min_level == 2


@pytest.mark.parametrize(
    "skill_id",
    [
        "skill:attack-boost",
        "skill:critical-eye",
        "wilds:skill:123456",
        "Skill:Internal_ID-01",
    ],
)
def test_skill_requirement_preserves_skill_id_without_normalization(
    skill_id: str,
) -> None:
    assert requirement(skill_id=skill_id).skill_id == skill_id


@pytest.mark.parametrize("min_level", [1, 999])
def test_skill_requirement_accepts_positive_min_levels(min_level: int) -> None:
    assert requirement(min_level=min_level).min_level == min_level


def test_skill_requirement_value_semantics() -> None:
    assert requirement() == requirement()
    assert requirement() != requirement(skill_id="skill:critical-eye")
    assert requirement() != requirement(min_level=2)


def test_skill_requirement_is_hashable() -> None:
    assert {requirement(), requirement()} == {requirement()}


def test_skill_requirement_is_frozen() -> None:
    value = requirement()

    with pytest.raises(FrozenInstanceError):
        value.min_level = 2  # type: ignore[misc]


def test_solver_package_exports_skill_requirement() -> None:
    from mhwilds_skill_sim.solver import SkillRequirement as ExportedRequirement

    assert ExportedRequirement is SkillRequirement


@pytest.mark.parametrize(
    "skill_id",
    ["", " ", "\t", " skill:attack-boost", "skill:attack-boost "],
)
def test_skill_requirement_rejects_invalid_skill_id_text(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_id"):
        requirement(skill_id=skill_id)


@pytest.mark.parametrize("skill_id", [1, None])
def test_skill_requirement_rejects_non_string_skill_id(skill_id: object) -> None:
    with pytest.raises(TypeError, match="skill_id"):
        SkillRequirement(skill_id=skill_id, min_level=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("min_level", [0, -1])
def test_skill_requirement_rejects_non_positive_min_level(min_level: int) -> None:
    with pytest.raises(ValueError, match="min_level"):
        requirement(min_level=min_level)


@pytest.mark.parametrize("min_level", [True, 1.5, "1", None])
def test_skill_requirement_rejects_non_int_min_level(min_level: object) -> None:
    with pytest.raises(TypeError, match="min_level"):
        SkillRequirement(
            skill_id="skill:attack-boost",
            min_level=min_level,  # type: ignore[arg-type]
        )


def test_empty_requirements_are_satisfied() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={},
        requirements=(),
    )


def test_exact_level_satisfies_requirement() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={"skill:attack-boost": 2},
        requirements=(requirement(min_level=2),),
    )


def test_larger_level_satisfies_requirement() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={"skill:attack-boost": 3},
        requirements=(requirement(min_level=2),),
    )


def test_smaller_level_does_not_satisfy_requirement() -> None:
    assert not skill_levels_satisfy_requirements(
        skill_levels={"skill:attack-boost": 1},
        requirements=(requirement(min_level=2),),
    )


def test_missing_required_skill_does_not_satisfy_requirement() -> None:
    assert not skill_levels_satisfy_requirements(
        skill_levels={},
        requirements=(requirement(),),
    )


def test_multiple_requirements_are_satisfied_when_all_levels_are_large_enough() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={
            "skill:attack-boost": 2,
            "skill:critical-eye": 3,
        },
        requirements=(
            requirement("skill:attack-boost", 1),
            requirement("skill:critical-eye", 3),
        ),
    )


def test_multiple_requirements_fail_when_any_level_is_too_small() -> None:
    assert not skill_levels_satisfy_requirements(
        skill_levels={
            "skill:attack-boost": 2,
            "skill:critical-eye": 2,
        },
        requirements=(
            requirement("skill:attack-boost", 1),
            requirement("skill:critical-eye", 3),
        ),
    )


def test_extra_skill_levels_are_ignored() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={
            "skill:attack-boost": 1,
            "skill:unused": 999,
        },
        requirements=(requirement(),),
    )


def test_skill_id_text_is_not_normalized_during_requirement_matching() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={"Skill:Internal_ID-01": 1},
        requirements=(requirement("Skill:Internal_ID-01"),),
    )
    assert not skill_levels_satisfy_requirements(
        skill_levels={"Skill:Internal_ID-01": 1},
        requirements=(requirement("skill:internal_id-01"),),
    )


def test_skill_levels_accept_zero_values() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={"skill:attack-boost": 0},
        requirements=(),
    )
    assert not skill_levels_satisfy_requirements(
        skill_levels={"skill:attack-boost": 0},
        requirements=(requirement(),),
    )


def test_skill_levels_accept_large_values_without_cap() -> None:
    assert skill_levels_satisfy_requirements(
        skill_levels={"skill:attack-boost": 10_000},
        requirements=(requirement(min_level=9_999),),
    )


def test_inputs_are_not_modified() -> None:
    skill_levels = {"skill:attack-boost": 1}
    requirements = (requirement(),)
    original_skill_levels = dict(skill_levels)
    original_requirements = requirements

    skill_levels_satisfy_requirements(
        skill_levels=skill_levels,
        requirements=requirements,
    )

    assert skill_levels == original_skill_levels
    assert requirements == original_requirements


def test_skill_levels_satisfy_requirements_requires_keyword_arguments() -> None:
    signature = inspect.signature(skill_levels_satisfy_requirements)

    assert signature.parameters["skill_levels"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["requirements"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        skill_levels_satisfy_requirements({}, ())  # type: ignore[call-arg]


def test_solver_package_exports_skill_levels_satisfy_requirements() -> None:
    from mhwilds_skill_sim.solver import (
        skill_levels_satisfy_requirements as exported_function,
    )

    assert exported_function is skill_levels_satisfy_requirements


def test_solver_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.solver import (
        enumerate_decoration_placement_combinations as exported_decorations,
    )
    from mhwilds_skill_sim.solver import (
        enumerate_equipment_selections as exported_equipment,
    )

    assert exported_decorations is enumerate_decoration_placement_combinations
    assert exported_equipment is enumerate_equipment_selections


@pytest.mark.parametrize("skill_levels", [[], set(), (), None])
def test_rejects_non_dict_skill_levels(skill_levels: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        skill_levels_satisfy_requirements(
            skill_levels=skill_levels,  # type: ignore[arg-type]
            requirements=(),
        )


def test_rejects_skill_levels_dict_subclass() -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        skill_levels_satisfy_requirements(
            skill_levels=SkillLevelDict({"skill:attack-boost": 1}),
            requirements=(),
        )


@pytest.mark.parametrize("skill_id", [1, None])
def test_rejects_non_string_skill_level_keys(skill_id: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        skill_levels_satisfy_requirements(
            skill_levels={skill_id: 1},  # type: ignore[dict-item]
            requirements=(),
        )


@pytest.mark.parametrize(
    "skill_id",
    ["", " ", "\t", " skill:attack-boost", "skill:attack-boost "],
)
def test_rejects_invalid_skill_level_key_text(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        skill_levels_satisfy_requirements(
            skill_levels={skill_id: 1},
            requirements=(),
        )


@pytest.mark.parametrize("level", [True, 1.5, "1", None])
def test_rejects_non_int_skill_level_values(level: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        skill_levels_satisfy_requirements(
            skill_levels={"skill:attack-boost": level},  # type: ignore[dict-item]
            requirements=(),
        )


def test_rejects_negative_skill_level_values() -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        skill_levels_satisfy_requirements(
            skill_levels={"skill:attack-boost": -1},
            requirements=(),
        )


@pytest.mark.parametrize(
    "requirements",
    [[requirement()], {requirement()}, requirement_generator(), None],
)
def test_rejects_non_tuple_requirements(requirements: object) -> None:
    with pytest.raises(TypeError, match="requirements"):
        skill_levels_satisfy_requirements(
            skill_levels={},
            requirements=requirements,  # type: ignore[arg-type]
        )


def test_rejects_requirements_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="requirements"):
        skill_levels_satisfy_requirements(
            skill_levels={},
            requirements=RequirementTuple((requirement(),)),
        )


@pytest.mark.parametrize("invalid_requirement", ["skill:attack-boost", None])
def test_rejects_invalid_requirement_elements(invalid_requirement: object) -> None:
    with pytest.raises(TypeError, match="requirements"):
        skill_levels_satisfy_requirements(
            skill_levels={},
            requirements=(invalid_requirement,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_requirement_skill_ids() -> None:
    with pytest.raises(ValueError, match="requirements"):
        skill_levels_satisfy_requirements(
            skill_levels={},
            requirements=(
                requirement("skill:attack-boost", 1),
                requirement("skill:attack-boost", 2),
            ),
        )
