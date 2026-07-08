from __future__ import annotations

from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.decoration import (
    enumerate_decoration_placement_combinations,
)
from mhwilds_skill_sim.solver.equipment import enumerate_equipment_selections
from mhwilds_skill_sim.validation.placement import DecorationPlacement


def skill() -> SkillContribution:
    return SkillContribution("skill:attack-boost", 1)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def equipment_definition(
    equipment_id: str = "equipment:weapon",
    *,
    part: EquipmentPart = EquipmentPart.WEAPON,
    slots: tuple[DecorationSlot, ...] = (),
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=(),
        slots=slots,
    )


def decoration_definition(
    decoration_id: str = "decoration:weapon-1",
    *,
    required_slot: DecorationSlot | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=required_slot or weapon_slot(1),
        skills=(skill(),),
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


def enumerate_combinations(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    decorations: tuple[DecorationDefinition, ...] | None = None,
) -> tuple[tuple[DecorationPlacement, ...], ...]:
    return enumerate_decoration_placement_combinations(
        equipment=equipment
        if equipment is not None
        else (equipment_definition(slots=(weapon_slot(1),)),),
        decorations=decorations
        if decorations is not None
        else (decoration_definition(required_slot=weapon_slot(1)),),
    )


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition(slots=(weapon_slot(1),))


def decoration_generator() -> Iterator[DecorationDefinition]:
    yield decoration_definition()


class EquipmentTuple(tuple):
    pass


class DecorationTuple(tuple):
    pass


def test_empty_equipment_returns_empty_placement_combination() -> None:
    assert enumerate_combinations(equipment=()) == ((),)


def test_equipment_without_slots_returns_empty_placement_combination() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=()),),
    ) == ((),)


def test_empty_decorations_returns_empty_placement_combination() -> None:
    assert enumerate_combinations(decorations=()) == ((),)


def test_no_compatible_decorations_returns_empty_placement_combination() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(armor_slot(1),)),),
        decorations=(decoration_definition(required_slot=weapon_slot(1)),),
    ) == ((),)


def test_one_slot_with_one_compatible_decoration_returns_empty_and_one_placement() -> (
    None
):
    assert enumerate_combinations() == (
        (),
        (placement(),),
    )


def test_one_slot_with_two_compatible_decorations_keeps_decoration_input_order() -> (
    None
):
    assert enumerate_combinations(
        decorations=(
            decoration_definition("decoration:weapon-a", required_slot=weapon_slot(1)),
            decoration_definition("decoration:weapon-b", required_slot=weapon_slot(1)),
        ),
    ) == (
        (),
        (placement(decoration_id="decoration:weapon-a"),),
        (placement(decoration_id="decoration:weapon-b"),),
    )


def test_two_slots_with_one_compatible_decoration_each_returns_four_combinations() -> (
    None
):
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(weapon_slot(1), armor_slot(1))),),
        decorations=(
            decoration_definition("decoration:weapon", required_slot=weapon_slot(1)),
            decoration_definition("decoration:armor", required_slot=armor_slot(1)),
        ),
    ) == (
        (),
        (placement(slot_index=1, decoration_id="decoration:armor"),),
        (placement(slot_index=0, decoration_id="decoration:weapon"),),
        (
            placement(slot_index=0, decoration_id="decoration:weapon"),
            placement(slot_index=1, decoration_id="decoration:armor"),
        ),
    )


def test_two_slots_with_only_one_compatible_slot_returns_two_combinations() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(weapon_slot(1), armor_slot(1))),),
        decorations=(decoration_definition(required_slot=weapon_slot(1)),),
    ) == (
        (),
        (placement(slot_index=0),),
    )


def test_weapon_slot_uses_only_weapon_decorations() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(weapon_slot(1),)),),
        decorations=(
            decoration_definition("decoration:weapon", required_slot=weapon_slot(1)),
            decoration_definition("decoration:armor", required_slot=armor_slot(1)),
        ),
    ) == (
        (),
        (placement(decoration_id="decoration:weapon"),),
    )


def test_armor_slot_uses_only_armor_decorations() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(armor_slot(1),)),),
        decorations=(
            decoration_definition("decoration:weapon", required_slot=weapon_slot(1)),
            decoration_definition("decoration:armor", required_slot=armor_slot(1)),
        ),
    ) == (
        (),
        (placement(decoration_id="decoration:armor"),),
    )


def test_rejects_decoration_when_required_level_exceeds_available_level() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(weapon_slot(1),)),),
        decorations=(decoration_definition(required_slot=weapon_slot(2)),),
    ) == ((),)


def test_accepts_decoration_when_available_level_is_large_enough() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(weapon_slot(2),)),),
        decorations=(decoration_definition(required_slot=weapon_slot(1)),),
    ) == (
        (),
        (placement(),),
    )


def test_includes_same_decoration_id_on_multiple_slots() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(weapon_slot(1), weapon_slot(1))),),
        decorations=(decoration_definition("decoration:shared"),),
    )[-1] == (
        placement(slot_index=0, decoration_id="decoration:shared"),
        placement(slot_index=1, decoration_id="decoration:shared"),
    )


def test_empty_placement_combination_is_first() -> None:
    assert enumerate_combinations()[0] == ()


def test_placement_tuple_order_follows_slot_traversal_order() -> None:
    result = enumerate_combinations(
        equipment=(
            equipment_definition("equipment:first", slots=(weapon_slot(1),)),
            equipment_definition("equipment:second", slots=(weapon_slot(1),)),
        ),
        decorations=(decoration_definition(),),
    )[-1]

    assert result == (
        placement("equipment:first", 0, "decoration:weapon-1"),
        placement("equipment:second", 0, "decoration:weapon-1"),
    )


def test_combination_order_is_deterministic_product_order() -> None:
    combinations = enumerate_combinations(
        equipment=(
            equipment_definition("equipment:first", slots=(weapon_slot(1),)),
            equipment_definition("equipment:second", slots=(armor_slot(1),)),
        ),
        decorations=(
            decoration_definition("decoration:weapon", required_slot=weapon_slot(1)),
            decoration_definition("decoration:armor", required_slot=armor_slot(1)),
        ),
    )

    assert combinations == (
        (),
        (placement("equipment:second", 0, "decoration:armor"),),
        (placement("equipment:first", 0, "decoration:weapon"),),
        (
            placement("equipment:first", 0, "decoration:weapon"),
            placement("equipment:second", 0, "decoration:armor"),
        ),
    )


def test_outer_return_value_and_each_combination_are_tuples() -> None:
    result = enumerate_combinations()

    assert type(result) is tuple
    assert all(type(combination) is tuple for combination in result)


def test_returns_new_tuple_each_call() -> None:
    first = enumerate_combinations()
    second = enumerate_combinations()

    assert first == second
    assert first is not second


def test_inputs_are_not_modified() -> None:
    equipment = (equipment_definition(slots=(weapon_slot(1),)),)
    decorations = (decoration_definition(),)
    equipment_before = equipment
    decorations_before = decorations

    enumerate_decoration_placement_combinations(
        equipment=equipment,
        decorations=decorations,
    )

    assert equipment == equipment_before
    assert decorations == decorations_before


def test_solver_package_exports_enumerate_decoration_placement_combinations() -> None:
    from mhwilds_skill_sim.solver import (
        enumerate_decoration_placement_combinations as exported_function,
    )

    assert exported_function is enumerate_decoration_placement_combinations


def test_solver_package_keeps_equipment_enumeration_export() -> None:
    from mhwilds_skill_sim.solver import (
        enumerate_equipment_selections as exported_function,
    )

    assert exported_function is enumerate_equipment_selections


def test_enumerate_decoration_placement_combinations_requires_keyword_arguments() -> (
    None
):
    with pytest.raises(TypeError):
        enumerate_decoration_placement_combinations((), ())  # type: ignore[misc]


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_definition(slots=(weapon_slot(1),))],
        {equipment_definition(slots=(weapon_slot(1),))},
        equipment_generator(),
        None,
        EquipmentTuple((equipment_definition(slots=(weapon_slot(1),)),)),
    ],
)
def test_rejects_non_tuple_equipment(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        enumerate_decoration_placement_combinations(
            equipment=equipment,  # type: ignore[arg-type]
            decorations=(),
        )


@pytest.mark.parametrize(
    "decorations",
    [
        [decoration_definition()],
        {decoration_definition()},
        decoration_generator(),
        None,
        DecorationTuple((decoration_definition(),)),
    ],
)
def test_rejects_non_tuple_decorations(decorations: object) -> None:
    with pytest.raises(TypeError, match="decorations"):
        enumerate_decoration_placement_combinations(
            equipment=(),
            decorations=decorations,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_equipment", ["equipment:weapon", None])
def test_rejects_invalid_equipment_elements(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        enumerate_decoration_placement_combinations(
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
            decorations=(),
        )


@pytest.mark.parametrize("invalid_decoration", ["decoration:weapon", None])
def test_rejects_invalid_decoration_elements(invalid_decoration: object) -> None:
    with pytest.raises(TypeError, match="decorations"):
        enumerate_decoration_placement_combinations(
            equipment=(),
            decorations=(invalid_decoration,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_equipment_id() -> None:
    with pytest.raises(ValueError, match="equipment"):
        enumerate_decoration_placement_combinations(
            equipment=(
                equipment_definition("equipment:duplicate"),
                equipment_definition("equipment:duplicate"),
            ),
            decorations=(),
        )


def test_rejects_duplicate_decoration_id() -> None:
    with pytest.raises(ValueError, match="decorations"):
        enumerate_decoration_placement_combinations(
            equipment=(),
            decorations=(
                decoration_definition("decoration:duplicate"),
                decoration_definition("decoration:duplicate"),
            ),
        )


def test_allows_same_text_in_equipment_id_and_decoration_id() -> None:
    assert enumerate_decoration_placement_combinations(
        equipment=(equipment_definition("shared:id", slots=(weapon_slot(1),)),),
        decorations=(decoration_definition("shared:id"),),
    ) == (
        (),
        (placement("shared:id", 0, "shared:id"),),
    )


def test_does_not_require_seven_equipment_parts() -> None:
    assert enumerate_combinations(
        equipment=(equipment_definition(slots=(weapon_slot(1),)),),
    ) == (
        (),
        (placement(),),
    )


def test_weapon_part_with_armor_slot_uses_armor_decorations() -> None:
    assert enumerate_combinations(
        equipment=(
            equipment_definition(
                part=EquipmentPart.WEAPON,
                slots=(armor_slot(1),),
            ),
        ),
        decorations=(decoration_definition(required_slot=armor_slot(1)),),
    ) == (
        (),
        (placement(),),
    )


def test_head_part_with_weapon_slot_uses_weapon_decorations() -> None:
    assert enumerate_combinations(
        equipment=(
            equipment_definition(
                part=EquipmentPart.HEAD,
                slots=(weapon_slot(1),),
            ),
        ),
        decorations=(decoration_definition(required_slot=weapon_slot(1)),),
    ) == (
        (),
        (placement(),),
    )
