from __future__ import annotations

import inspect
from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

import mhwilds_skill_sim.solver as solver_package
from mhwilds_skill_sim.solver.preferences import (
    SkillPreference,
    calculate_skill_preference_score,
)


def preference(
    skill_id: str = "skill:attack-boost",
    target_level: int = 1,
) -> SkillPreference:
    return SkillPreference(skill_id=skill_id, target_level=target_level)


def preference_generator() -> Iterator[SkillPreference]:
    yield preference()


class SkillId(str):
    pass


class SkillLevel(int):
    pass


class SkillLevelDict(dict[str, int]):
    pass


class PreferenceTuple(tuple):
    pass


def test_skill_preference_keeps_valid_values() -> None:
    value = SkillPreference(skill_id="skill:attack-boost", target_level=2)

    assert value.skill_id == "skill:attack-boost"
    assert value.target_level == 2


@pytest.mark.parametrize(
    "skill_id",
    [
        "skill:attack-boost",
        "skill:critical-eye",
        "wilds:skill:123456",
        "Skill:Internal ID_01",
    ],
)
def test_skill_preference_preserves_skill_id_without_normalization(
    skill_id: str,
) -> None:
    assert preference(skill_id=skill_id).skill_id == skill_id


@pytest.mark.parametrize("target_level", [1, 999_999])
def test_skill_preference_accepts_positive_target_levels(target_level: int) -> None:
    assert preference(target_level=target_level).target_level == target_level


def test_skill_preference_value_semantics() -> None:
    assert preference() == preference()
    assert preference() != preference(skill_id="skill:critical-eye")
    assert preference() != preference(target_level=2)


def test_skill_preference_is_hashable() -> None:
    assert {preference(), preference()} == {preference()}


def test_skill_preference_is_frozen() -> None:
    value = preference()

    with pytest.raises(FrozenInstanceError):
        value.target_level = 2  # type: ignore[misc]


def test_skill_preference_uses_slots() -> None:
    value = preference()

    assert SkillPreference.__slots__ == ("skill_id", "target_level")
    assert not hasattr(value, "__dict__")


@pytest.mark.parametrize(
    "skill_id",
    ["", " ", "\t", " skill:attack-boost", "skill:attack-boost "],
)
def test_skill_preference_rejects_invalid_skill_id_text(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_id"):
        preference(skill_id=skill_id)


@pytest.mark.parametrize("skill_id", [1, None, SkillId("skill:attack-boost")])
def test_skill_preference_requires_exact_string_skill_id(skill_id: object) -> None:
    with pytest.raises(TypeError, match="skill_id"):
        SkillPreference(skill_id=skill_id, target_level=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("target_level", [0, -1])
def test_skill_preference_rejects_non_positive_target_level(
    target_level: int,
) -> None:
    with pytest.raises(ValueError, match="target_level"):
        preference(target_level=target_level)


@pytest.mark.parametrize(
    "target_level",
    [True, 1.5, "1", None, SkillLevel(1)],
)
def test_skill_preference_requires_exact_int_target_level(
    target_level: object,
) -> None:
    with pytest.raises(TypeError, match="target_level"):
        SkillPreference(
            skill_id="skill:attack-boost",
            target_level=target_level,  # type: ignore[arg-type]
        )


def test_skill_preference_is_imported_directly_from_its_module() -> None:
    from mhwilds_skill_sim.solver.preferences import (
        SkillPreference as DirectSkillPreference,
    )

    assert DirectSkillPreference is SkillPreference


def test_solver_package_does_not_export_skill_preferences() -> None:
    assert not hasattr(solver_package, "SkillPreference")
    assert not hasattr(solver_package, "calculate_skill_preference_score")


def test_solver_package_all_is_unchanged() -> None:
    assert solver_package.__all__ == [
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


def test_empty_preferences_score_zero() -> None:
    assert (
        calculate_skill_preference_score(
            skill_levels={"skill:attack-boost": 5},
            preferences=(),
        )
        == 0
    )


def test_missing_preferred_skill_scores_zero() -> None:
    assert (
        calculate_skill_preference_score(
            skill_levels={},
            preferences=(preference(target_level=3),),
        )
        == 0
    )


def test_skill_preference_score_caps_level_at_target() -> None:
    assert (
        calculate_skill_preference_score(
            skill_levels={"skill:attack-boost": 5},
            preferences=(preference(target_level=3),),
        )
        == 3
    )


def test_skill_preference_score_sums_multiple_skills() -> None:
    preferences = (
        preference("skill:attack-boost", 3),
        preference("skill:critical-eye", 5),
        preference("skill:weakness-exploit", 1),
    )

    assert (
        calculate_skill_preference_score(
            skill_levels={
                "skill:attack-boost": 4,
                "skill:critical-eye": 2,
            },
            preferences=preferences,
        )
        == 5
    )


def test_zero_skill_level_scores_zero() -> None:
    assert (
        calculate_skill_preference_score(
            skill_levels={"skill:attack-boost": 0},
            preferences=(preference(target_level=3),),
        )
        == 0
    )


def test_skill_preference_score_does_not_depend_on_preference_order() -> None:
    first = preference("skill:attack-boost", 3)
    second = preference("skill:critical-eye", 5)
    skill_levels = {
        "skill:attack-boost": 4,
        "skill:critical-eye": 2,
    }

    assert calculate_skill_preference_score(
        skill_levels=skill_levels,
        preferences=(first, second),
    ) == calculate_skill_preference_score(
        skill_levels=skill_levels,
        preferences=(second, first),
    )


def test_calculate_skill_preference_score_returns_exact_int() -> None:
    score = calculate_skill_preference_score(
        skill_levels={"skill:attack-boost": 1},
        preferences=(preference(),),
    )

    assert type(score) is int


def test_calculate_skill_preference_score_requires_keyword_arguments() -> None:
    signature = inspect.signature(calculate_skill_preference_score)

    assert signature.parameters["skill_levels"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["preferences"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        calculate_skill_preference_score({}, ())  # type: ignore[call-arg]


@pytest.mark.parametrize("skill_levels", [[], set(), (), None])
def test_score_rejects_non_dict_skill_levels(skill_levels: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        calculate_skill_preference_score(
            skill_levels=skill_levels,  # type: ignore[arg-type]
            preferences=(),
        )


def test_score_rejects_skill_levels_dict_subclass() -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        calculate_skill_preference_score(
            skill_levels=SkillLevelDict({"skill:attack-boost": 1}),
            preferences=(),
        )


@pytest.mark.parametrize("skill_id", [1, None, SkillId("skill:attack-boost")])
def test_score_rejects_non_exact_string_skill_level_keys(skill_id: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        calculate_skill_preference_score(
            skill_levels={skill_id: 1},  # type: ignore[dict-item]
            preferences=(),
        )


@pytest.mark.parametrize(
    "skill_id",
    ["", " ", "\t", " skill:attack-boost", "skill:attack-boost "],
)
def test_score_rejects_invalid_skill_level_key_text(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        calculate_skill_preference_score(
            skill_levels={skill_id: 1},
            preferences=(),
        )


@pytest.mark.parametrize("level", [True, 1.5, "1", None, SkillLevel(1)])
def test_score_rejects_non_exact_int_skill_levels(level: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        calculate_skill_preference_score(
            skill_levels={"skill:attack-boost": level},  # type: ignore[dict-item]
            preferences=(),
        )


def test_score_rejects_negative_skill_level() -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        calculate_skill_preference_score(
            skill_levels={"skill:attack-boost": -1},
            preferences=(),
        )


@pytest.mark.parametrize(
    "preferences",
    [[preference()], {preference()}, preference_generator(), None],
)
def test_score_rejects_non_tuple_preferences(preferences: object) -> None:
    with pytest.raises(TypeError, match="preferences"):
        calculate_skill_preference_score(
            skill_levels={},
            preferences=preferences,  # type: ignore[arg-type]
        )


def test_score_rejects_preference_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="preferences"):
        calculate_skill_preference_score(
            skill_levels={},
            preferences=PreferenceTuple((preference(),)),
        )


@pytest.mark.parametrize("invalid_preference", ["skill:attack-boost", None])
def test_score_rejects_invalid_preference_items(invalid_preference: object) -> None:
    with pytest.raises(TypeError, match="preferences"):
        calculate_skill_preference_score(
            skill_levels={},
            preferences=(invalid_preference,),  # type: ignore[arg-type]
        )


def test_score_rejects_duplicate_preference_skill_ids() -> None:
    with pytest.raises(ValueError, match="preferences"):
        calculate_skill_preference_score(
            skill_levels={},
            preferences=(
                preference("skill:attack-boost", 1),
                preference("skill:attack-boost", 2),
            ),
        )


def test_score_inputs_are_not_modified() -> None:
    skill_levels = {
        "skill:attack-boost": 4,
        "skill:critical-eye": 2,
    }
    preferences = (
        preference("skill:attack-boost", 3),
        preference("skill:critical-eye", 5),
    )
    original_skill_levels = dict(skill_levels)
    original_preferences = preferences

    calculate_skill_preference_score(
        skill_levels=skill_levels,
        preferences=preferences,
    )

    assert skill_levels == original_skill_levels
    assert preferences == original_preferences


def test_score_is_deterministic_across_repeated_calls() -> None:
    skill_levels = {"skill:attack-boost": 4}
    preferences = (preference(target_level=3),)

    scores = [
        calculate_skill_preference_score(
            skill_levels=skill_levels,
            preferences=preferences,
        )
        for _ in range(10)
    ]

    assert scores == [3] * 10
