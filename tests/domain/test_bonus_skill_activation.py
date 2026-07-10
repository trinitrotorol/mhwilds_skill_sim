from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain.bonus import (
    calculate_equipment_bonus_skill_contributions,
)
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
    aggregate_skill_levels,
)


def equipment_definition(
    equipment_id: str,
    *,
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=EquipmentPart.HEAD,
        skills=(),
        slots=(),
        series_skill_id=series_skill_id,
        group_skill_id=group_skill_id,
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
    skill_id: str,
    kind: SkillKind,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=(SkillRankDefinition(level=1, required_pieces=None),),
    )


def series_equipment(
    count: int,
    skill_id: str = "skill:series-bonus",
) -> tuple[EquipmentDefinition, ...]:
    return tuple(
        equipment_definition(
            f"equipment:series:{index}",
            series_skill_id=skill_id,
        )
        for index in range(count)
    )


def group_equipment(
    count: int,
    skill_id: str = "skill:group-bonus",
) -> tuple[EquipmentDefinition, ...]:
    return tuple(
        equipment_definition(
            f"equipment:group:{index}",
            group_skill_id=skill_id,
        )
        for index in range(count)
    )


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition("equipment:head")


def skill_definition_generator() -> Iterator[SkillDefinition]:
    yield series_skill_definition()


class EquipmentTuple(tuple):
    pass


class SkillDefinitionTuple(tuple):
    pass


def calculate(
    *,
    equipment: tuple[EquipmentDefinition, ...] = (),
    skill_definitions: tuple[SkillDefinition, ...] = (),
) -> tuple[SkillContribution, ...]:
    return calculate_equipment_bonus_skill_contributions(
        equipment=equipment,
        skill_definitions=skill_definitions,
    )


def test_empty_equipment_and_definitions_return_empty_tuple() -> None:
    result = calculate()

    assert type(result) is tuple
    assert result == ()


def test_bonus_definitions_without_memberships_return_empty_tuple() -> None:
    assert (
        calculate(
            skill_definitions=(series_skill_definition(), group_skill_definition()),
        )
        == ()
    )


def test_below_first_series_threshold_returns_no_contribution() -> None:
    assert (
        calculate(
            equipment=series_equipment(1),
            skill_definitions=(series_skill_definition(),),
        )
        == ()
    )


def test_exact_first_series_threshold_activates_level_one() -> None:
    assert calculate(
        equipment=series_equipment(2),
        skill_definitions=(series_skill_definition(),),
    ) == (SkillContribution("skill:series-bonus", 1),)


def test_series_count_between_thresholds_keeps_lower_level() -> None:
    assert calculate(
        equipment=series_equipment(3),
        skill_definitions=(series_skill_definition(),),
    ) == (SkillContribution("skill:series-bonus", 1),)


def test_exact_higher_series_threshold_activates_higher_level() -> None:
    assert calculate(
        equipment=series_equipment(4),
        skill_definitions=(series_skill_definition(),),
    ) == (SkillContribution("skill:series-bonus", 2),)


def test_series_count_above_maximum_keeps_highest_level() -> None:
    assert calculate(
        equipment=series_equipment(6),
        skill_definitions=(series_skill_definition(),),
    ) == (SkillContribution("skill:series-bonus", 2),)


def test_group_threshold_activates_group_level() -> None:
    assert calculate(
        equipment=group_equipment(3),
        skill_definitions=(group_skill_definition(),),
    ) == (SkillContribution("skill:group-bonus", 1),)


def test_simultaneous_series_and_group_activation() -> None:
    equipment = tuple(
        equipment_definition(
            f"equipment:both:{index}",
            series_skill_id="skill:series-bonus",
            group_skill_id="skill:group-bonus",
        )
        for index in range(3)
    )

    assert calculate(
        equipment=equipment,
        skill_definitions=(series_skill_definition(), group_skill_definition()),
    ) == (
        SkillContribution("skill:series-bonus", 1),
        SkillContribution("skill:group-bonus", 1),
    )


def test_one_item_contributes_to_both_bonus_categories() -> None:
    equipment = (
        equipment_definition(
            "equipment:both",
            series_skill_id="skill:series-bonus",
            group_skill_id="skill:group-bonus",
        ),
    )

    assert calculate(
        equipment=equipment,
        skill_definitions=(
            series_skill_definition(thresholds=(1,)),
            group_skill_definition(thresholds=(1,)),
        ),
    ) == (
        SkillContribution("skill:series-bonus", 1),
        SkillContribution("skill:group-bonus", 1),
    )


def test_multiple_bonus_skill_ids_activate_independently() -> None:
    equipment = (
        *series_equipment(2, "skill:series-a"),
        *series_equipment(1, "skill:series-b"),
        *group_equipment(2, "skill:group-a"),
    )

    assert calculate(
        equipment=equipment,
        skill_definitions=(
            series_skill_definition("skill:series-a", (2,)),
            series_skill_definition("skill:series-b", (1,)),
            group_skill_definition("skill:group-a", (2,)),
        ),
    ) == (
        SkillContribution("skill:series-a", 1),
        SkillContribution("skill:series-b", 1),
        SkillContribution("skill:group-a", 1),
    )


def test_output_order_follows_skill_definition_order() -> None:
    equipment = (
        *series_equipment(1, "skill:series-a"),
        *group_equipment(1, "skill:group-a"),
        *series_equipment(1, "skill:series-b"),
    )

    result = calculate(
        equipment=equipment,
        skill_definitions=(
            series_skill_definition("skill:series-b", (1,)),
            group_skill_definition("skill:group-a", (1,)),
            series_skill_definition("skill:series-a", (1,)),
        ),
    )

    assert tuple(contribution.skill_id for contribution in result) == (
        "skill:series-b",
        "skill:group-a",
        "skill:series-a",
    )


def test_armor_and_weapon_definitions_are_ignored_for_activation() -> None:
    result = calculate(
        equipment=series_equipment(1),
        skill_definitions=(
            normal_skill_definition("skill:armor", SkillKind.ARMOR),
            series_skill_definition(thresholds=(1,)),
            normal_skill_definition("skill:weapon", SkillKind.WEAPON),
        ),
    )

    assert result == (SkillContribution("skill:series-bonus", 1),)


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_definition("equipment:head")],
        {equipment_definition("equipment:head")},
        equipment_generator(),
        None,
    ],
)
def test_rejects_non_tuple_equipment(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        calculate_equipment_bonus_skill_contributions(
            equipment=equipment,  # type: ignore[arg-type]
            skill_definitions=(),
        )


def test_rejects_equipment_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="equipment"):
        calculate(
            equipment=EquipmentTuple((equipment_definition("equipment:head"),)),
        )


@pytest.mark.parametrize("invalid_equipment", ["equipment", None, 1])
def test_rejects_invalid_equipment_elements(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        calculate(
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "skill_definitions",
    [
        [series_skill_definition()],
        {series_skill_definition()},
        skill_definition_generator(),
        None,
    ],
)
def test_rejects_non_tuple_skill_definitions(skill_definitions: object) -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        calculate_equipment_bonus_skill_contributions(
            equipment=(),
            skill_definitions=skill_definitions,  # type: ignore[arg-type]
        )


def test_rejects_skill_definitions_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        calculate(
            skill_definitions=SkillDefinitionTuple((series_skill_definition(),)),
        )


@pytest.mark.parametrize("invalid_definition", ["skill", None, 1])
def test_rejects_invalid_skill_definition_elements(
    invalid_definition: object,
) -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        calculate(
            skill_definitions=(invalid_definition,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_skill_definition_ids() -> None:
    with pytest.raises(ValueError, match="skill_definitions"):
        calculate(
            skill_definitions=(
                series_skill_definition("skill:duplicate", (1,)),
                group_skill_definition("skill:duplicate", (1,)),
            ),
        )


@pytest.mark.parametrize(
    ("field_name", "missing_skill_id"),
    [
        ("series_skill_id", "skill:missing-series"),
        ("group_skill_id", "skill:missing-group"),
    ],
)
def test_rejects_unknown_membership_references(
    field_name: str,
    missing_skill_id: str,
) -> None:
    memberships = {field_name: missing_skill_id}
    equipment = EquipmentDefinition(
        equipment_id="equipment:head",
        part=EquipmentPart.HEAD,
        skills=(),
        slots=(),
        **memberships,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError) as exc_info:
        calculate(equipment=(equipment,), skill_definitions=())

    assert "equipment" in str(exc_info.value)
    assert field_name in str(exc_info.value)


@pytest.mark.parametrize(
    "wrong_definition",
    [
        normal_skill_definition("skill:wrong", SkillKind.ARMOR),
        normal_skill_definition("skill:wrong", SkillKind.WEAPON),
        group_skill_definition("skill:wrong", (1,)),
    ],
)
def test_rejects_series_membership_referencing_wrong_kind(
    wrong_definition: SkillDefinition,
) -> None:
    equipment = equipment_definition(
        "equipment:head",
        series_skill_id=wrong_definition.skill_id,
    )

    with pytest.raises(ValueError) as exc_info:
        calculate(
            equipment=(equipment,),
            skill_definitions=(wrong_definition,),
        )

    assert "equipment" in str(exc_info.value)
    assert "series_skill_id" in str(exc_info.value)


@pytest.mark.parametrize(
    "wrong_definition",
    [
        normal_skill_definition("skill:wrong", SkillKind.ARMOR),
        normal_skill_definition("skill:wrong", SkillKind.WEAPON),
        series_skill_definition("skill:wrong", (1,)),
    ],
)
def test_rejects_group_membership_referencing_wrong_kind(
    wrong_definition: SkillDefinition,
) -> None:
    equipment = equipment_definition(
        "equipment:head",
        group_skill_id=wrong_definition.skill_id,
    )

    with pytest.raises(ValueError) as exc_info:
        calculate(
            equipment=(equipment,),
            skill_definitions=(wrong_definition,),
        )

    assert "equipment" in str(exc_info.value)
    assert "group_skill_id" in str(exc_info.value)


def test_inputs_are_not_modified() -> None:
    equipment = series_equipment(2)
    skill_definitions = (series_skill_definition(),)
    original_equipment = equipment
    original_skill_definitions = skill_definitions

    calculate(equipment=equipment, skill_definitions=skill_definitions)

    assert equipment == original_equipment
    assert skill_definitions == original_skill_definitions


def test_each_call_returns_a_new_nonempty_tuple() -> None:
    equipment = series_equipment(2)
    skill_definitions = (series_skill_definition(),)

    first = calculate(equipment=equipment, skill_definitions=skill_definitions)
    second = calculate(equipment=equipment, skill_definitions=skill_definitions)

    assert first == second
    assert first is not second


def test_function_arguments_are_keyword_only() -> None:
    signature = inspect.signature(calculate_equipment_bonus_skill_contributions)

    assert signature.parameters["equipment"].kind is inspect.Parameter.KEYWORD_ONLY
    assert (
        signature.parameters["skill_definitions"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    with pytest.raises(TypeError):
        calculate_equipment_bonus_skill_contributions((), ())  # type: ignore[misc]


def test_domain_package_exports_bonus_calculation() -> None:
    from mhwilds_skill_sim.domain import (
        calculate_equipment_bonus_skill_contributions as exported_calculation,
    )

    assert exported_calculation is calculate_equipment_bonus_skill_contributions


def test_existing_domain_exports_remain_available() -> None:
    from mhwilds_skill_sim.domain import (
        EquipmentDefinition as ExportedEquipmentDefinition,
    )
    from mhwilds_skill_sim.domain import SkillContribution as ExportedSkillContribution
    from mhwilds_skill_sim.domain import SkillDefinition as ExportedSkillDefinition
    from mhwilds_skill_sim.domain import SkillKind as ExportedSkillKind
    from mhwilds_skill_sim.domain import (
        aggregate_skill_levels as exported_aggregate_skill_levels,
    )

    assert ExportedEquipmentDefinition is EquipmentDefinition
    assert ExportedSkillContribution is SkillContribution
    assert ExportedSkillDefinition is SkillDefinition
    assert ExportedSkillKind is SkillKind
    assert exported_aggregate_skill_levels is aggregate_skill_levels
