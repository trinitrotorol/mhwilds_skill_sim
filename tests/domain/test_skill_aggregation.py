from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain import SkillContribution, aggregate_skill_levels


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id=skill_id, level=level)


def contribution_generator() -> Iterator[SkillContribution]:
    yield skill()


def test_aggregate_skill_levels_returns_empty_dict_for_empty_tuple() -> None:
    assert aggregate_skill_levels(contributions=()) == {}


def test_aggregate_skill_levels_aggregates_single_contribution() -> None:
    assert aggregate_skill_levels(contributions=(skill(),)) == {
        "skill:attack-boost": 1,
    }


def test_aggregate_skill_levels_aggregates_multiple_different_skill_ids() -> None:
    assert aggregate_skill_levels(
        contributions=(
            skill("skill:attack-boost", 1),
            skill("skill:critical-eye", 2),
            skill("skill:weakness-exploit", 3),
        ),
    ) == {
        "skill:attack-boost": 1,
        "skill:critical-eye": 2,
        "skill:weakness-exploit": 3,
    }


def test_aggregate_skill_levels_sums_duplicate_skill_id_levels() -> None:
    assert aggregate_skill_levels(
        contributions=(
            skill("skill:attack-boost", 1),
            skill("skill:critical-eye", 2),
            skill("skill:attack-boost", 3),
        ),
    ) == {
        "skill:attack-boost": 4,
        "skill:critical-eye": 2,
    }


def test_aggregate_skill_levels_sums_skill_id_seen_three_or_more_times() -> None:
    assert aggregate_skill_levels(
        contributions=(
            skill("skill:attack-boost", 1),
            skill("skill:attack-boost", 2),
            skill("skill:attack-boost", 3),
        ),
    ) == {"skill:attack-boost": 6}


def test_aggregate_skill_levels_keeps_distinct_skill_ids_separate() -> None:
    assert aggregate_skill_levels(
        contributions=(
            skill("skill:attack-boost", 1),
            skill("skill:attack-boost-plus", 1),
        ),
    ) == {
        "skill:attack-boost": 1,
        "skill:attack-boost-plus": 1,
    }


def test_aggregate_skill_levels_preserves_skill_id_text_without_normalization() -> None:
    assert aggregate_skill_levels(
        contributions=(
            skill("Skill:Internal_ID-01", 1),
            skill("skill:attack+boost/1", 2),
        ),
    ) == {
        "Skill:Internal_ID-01": 1,
        "skill:attack+boost/1": 2,
    }


def test_aggregate_skill_levels_accepts_large_total_levels_without_cap() -> None:
    assert aggregate_skill_levels(
        contributions=(
            skill("skill:attack-boost", 999),
            skill("skill:attack-boost", 1001),
        ),
    ) == {"skill:attack-boost": 2000}


def test_aggregate_skill_levels_returns_new_dict_each_call() -> None:
    first = aggregate_skill_levels(contributions=(skill(),))
    second = aggregate_skill_levels(contributions=(skill(),))

    assert first == second
    assert first is not second


def test_aggregate_skill_levels_result_mutation_does_not_affect_next_call() -> None:
    result = aggregate_skill_levels(contributions=(skill(),))
    result["skill:attack-boost"] = 999

    assert aggregate_skill_levels(contributions=(skill(),)) == {
        "skill:attack-boost": 1,
    }


def test_aggregate_skill_levels_preserves_first_seen_order() -> None:
    result = aggregate_skill_levels(
        contributions=(
            skill("skill:critical-eye", 1),
            skill("skill:attack-boost", 1),
            skill("skill:critical-eye", 2),
            skill("skill:weakness-exploit", 1),
        ),
    )

    assert list(result) == [
        "skill:critical-eye",
        "skill:attack-boost",
        "skill:weakness-exploit",
    ]
    assert result == {
        "skill:critical-eye": 3,
        "skill:attack-boost": 1,
        "skill:weakness-exploit": 1,
    }


def test_aggregate_skill_levels_arguments_are_keyword_only() -> None:
    signature = inspect.signature(aggregate_skill_levels)

    assert signature.parameters["contributions"].kind is (
        inspect.Parameter.KEYWORD_ONLY
    )

    with pytest.raises(TypeError):
        aggregate_skill_levels((skill(),))  # type: ignore[call-arg]


def test_domain_package_exports_aggregate_skill_levels() -> None:
    from mhwilds_skill_sim.domain import (
        aggregate_skill_levels as exported_aggregate_skill_levels,
    )

    assert exported_aggregate_skill_levels is aggregate_skill_levels


def test_domain_package_keeps_skill_contribution_export() -> None:
    from mhwilds_skill_sim.domain import SkillContribution as ExportedSkillContribution

    assert ExportedSkillContribution is SkillContribution


@pytest.mark.parametrize(
    "contributions",
    [
        [skill()],
        {skill()},
        contribution_generator(),
        None,
    ],
)
def test_aggregate_skill_levels_rejects_non_tuple_contributions(
    contributions: object,
) -> None:
    with pytest.raises(TypeError, match="contributions"):
        aggregate_skill_levels(contributions=contributions)  # type: ignore[arg-type]


def test_aggregate_skill_levels_rejects_tuple_subclass() -> None:
    class SkillTuple(tuple[SkillContribution, ...]):
        pass

    with pytest.raises(TypeError, match="contributions"):
        aggregate_skill_levels(contributions=SkillTuple((skill(),)))


@pytest.mark.parametrize("invalid_contribution", ["skill:attack-boost", None])
def test_aggregate_skill_levels_rejects_invalid_tuple_elements(
    invalid_contribution: object,
) -> None:
    with pytest.raises(TypeError, match="contributions"):
        aggregate_skill_levels(
            contributions=(invalid_contribution,),  # type: ignore[arg-type]
        )
