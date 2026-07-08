from __future__ import annotations

from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.solver.equipment import enumerate_equipment_selections


REQUIRED_PARTS = (
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
)


def equipment_definition(
    part: EquipmentPart,
    equipment_id: str | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=(),
        slots=(),
    )


def complete_equipment() -> tuple[EquipmentDefinition, ...]:
    return tuple(equipment_definition(part) for part in REQUIRED_PARTS)


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition(EquipmentPart.WEAPON)


class EquipmentTuple(tuple):
    pass


def equipment_ids(
    selections: tuple[tuple[EquipmentDefinition, ...], ...],
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(definition.equipment_id for definition in selection)
        for selection in selections
    )


def test_single_candidate_for_each_part_returns_one_selection() -> None:
    selections = enumerate_equipment_selections(equipment=complete_equipment())

    assert selections == (complete_equipment(),)


def test_selection_order_follows_required_equipment_part_order() -> None:
    selection = enumerate_equipment_selections(equipment=complete_equipment())[0]

    assert tuple(definition.part for definition in selection) == REQUIRED_PARTS


def test_input_order_can_be_different_from_selection_order() -> None:
    equipment = tuple(reversed(complete_equipment()))

    selection = enumerate_equipment_selections(equipment=equipment)[0]

    assert tuple(definition.part for definition in selection) == REQUIRED_PARTS


def test_two_head_candidates_return_two_selections() -> None:
    equipment = (
        equipment_definition(EquipmentPart.HEAD, "head:a"),
        equipment_definition(EquipmentPart.HEAD, "head:b"),
        *(
            equipment_definition(part)
            for part in REQUIRED_PARTS
            if part is not EquipmentPart.HEAD
        ),
    )

    selections = enumerate_equipment_selections(equipment=equipment)

    assert len(selections) == 2


def test_two_charm_candidates_return_two_selections() -> None:
    equipment = (
        equipment_definition(EquipmentPart.CHARM, "charm:a"),
        equipment_definition(EquipmentPart.CHARM, "charm:b"),
        *(
            equipment_definition(part)
            for part in REQUIRED_PARTS
            if part is not EquipmentPart.CHARM
        ),
    )

    selections = enumerate_equipment_selections(equipment=equipment)

    assert len(selections) == 2


def test_two_head_and_two_charm_candidates_return_four_selections() -> None:
    equipment = (
        equipment_definition(EquipmentPart.HEAD, "head:a"),
        equipment_definition(EquipmentPart.HEAD, "head:b"),
        equipment_definition(EquipmentPart.CHARM, "charm:a"),
        equipment_definition(EquipmentPart.CHARM, "charm:b"),
        *(
            equipment_definition(part)
            for part in REQUIRED_PARTS
            if part not in {EquipmentPart.HEAD, EquipmentPart.CHARM}
        ),
    )

    selections = enumerate_equipment_selections(equipment=equipment)

    assert len(selections) == 4


def test_candidate_order_within_same_part_follows_input_order() -> None:
    equipment = (
        equipment_definition(EquipmentPart.HEAD, "head:first"),
        equipment_definition(EquipmentPart.HEAD, "head:second"),
        *(
            equipment_definition(part)
            for part in REQUIRED_PARTS
            if part is not EquipmentPart.HEAD
        ),
    )

    selections = enumerate_equipment_selections(equipment=equipment)

    assert [selection[1].equipment_id for selection in selections] == [
        "head:first",
        "head:second",
    ]


def test_combination_order_matches_required_part_product_order() -> None:
    equipment = (
        equipment_definition(EquipmentPart.HEAD, "head:a"),
        equipment_definition(EquipmentPart.HEAD, "head:b"),
        equipment_definition(EquipmentPart.CHARM, "charm:a"),
        equipment_definition(EquipmentPart.CHARM, "charm:b"),
        equipment_definition(EquipmentPart.WEAPON, "weapon:a"),
        equipment_definition(EquipmentPart.CHEST, "chest:a"),
        equipment_definition(EquipmentPart.ARMS, "arms:a"),
        equipment_definition(EquipmentPart.WAIST, "waist:a"),
        equipment_definition(EquipmentPart.LEGS, "legs:a"),
    )

    selections = enumerate_equipment_selections(equipment=equipment)

    assert equipment_ids(selections) == (
        ("weapon:a", "head:a", "chest:a", "arms:a", "waist:a", "legs:a", "charm:a"),
        ("weapon:a", "head:a", "chest:a", "arms:a", "waist:a", "legs:a", "charm:b"),
        ("weapon:a", "head:b", "chest:a", "arms:a", "waist:a", "legs:a", "charm:a"),
        ("weapon:a", "head:b", "chest:a", "arms:a", "waist:a", "legs:a", "charm:b"),
    )


def test_each_selection_and_outer_return_value_are_tuples() -> None:
    selections = enumerate_equipment_selections(equipment=complete_equipment())

    assert type(selections) is tuple
    assert type(selections[0]) is tuple


def test_returns_new_tuple_each_call() -> None:
    first = enumerate_equipment_selections(equipment=complete_equipment())
    second = enumerate_equipment_selections(equipment=complete_equipment())

    assert first == second
    assert first is not second


def test_solver_package_exports_enumerate_equipment_selections() -> None:
    from mhwilds_skill_sim.solver import (
        enumerate_equipment_selections as exported_function,
    )

    assert exported_function is enumerate_equipment_selections


def test_enumerate_equipment_selections_requires_keyword_arguments() -> None:
    with pytest.raises(TypeError):
        enumerate_equipment_selections(complete_equipment())  # type: ignore[misc]


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
            if part is not EquipmentPart.HEAD
        ),
        tuple(
            equipment_definition(part)
            for part in REQUIRED_PARTS
            if part is not EquipmentPart.CHARM
        ),
        (
            equipment_definition(EquipmentPart.WEAPON),
            equipment_definition(EquipmentPart.HEAD),
        ),
    ],
)
def test_returns_empty_tuple_when_any_required_part_is_missing(
    equipment: tuple[EquipmentDefinition, ...],
) -> None:
    assert enumerate_equipment_selections(equipment=equipment) == ()


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_definition(EquipmentPart.WEAPON)],
        {equipment_definition(EquipmentPart.WEAPON)},
        equipment_generator(),
        None,
        EquipmentTuple((equipment_definition(EquipmentPart.WEAPON),)),
    ],
)
def test_rejects_non_tuple_equipment(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        enumerate_equipment_selections(equipment=equipment)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_equipment", ["equipment:weapon", None])
def test_rejects_invalid_equipment_elements(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        enumerate_equipment_selections(
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
        )


def test_duplicate_equipment_ids_are_not_rejected() -> None:
    equipment = tuple(
        equipment_definition(part, equipment_id="equipment:duplicate")
        for part in REQUIRED_PARTS
    )

    selections = enumerate_equipment_selections(equipment=equipment)

    assert len(selections) == 1


def test_input_equipment_is_not_modified() -> None:
    equipment = tuple(reversed(complete_equipment()))
    before = equipment

    enumerate_equipment_selections(equipment=equipment)

    assert equipment == before


def test_incomplete_selection_returns_empty_tuple_without_validation_error() -> None:
    assert (
        enumerate_equipment_selections(
            equipment=(equipment_definition(EquipmentPart.WEAPON),),
        )
        == ()
    )
