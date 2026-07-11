from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.solver.equipment_variants import (
    expand_equipment_bonus_skill_variants,
)


def skill(skill_id: str = "skill:attack-boost") -> SkillContribution:
    return SkillContribution(skill_id=skill_id, level=1)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(kind=DecorationKind.WEAPON, level=level)


def equipment_definition(
    equipment_id: str = "equipment:weapon:artian",
    *,
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=EquipmentPart.WEAPON,
        skills=(skill(),),
        slots=(weapon_slot(2),),
        series_skill_id=series_skill_id,
        group_skill_id=group_skill_id,
        allows_series_skill_assignment=allows_series_skill_assignment,
        allows_group_skill_assignment=allows_group_skill_assignment,
    )


def bonus_skill_definition(
    skill_id: str,
    kind: SkillKind,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=(SkillRankDefinition(level=1, required_pieces=1),),
    )


def series_skill_definition(skill_id: str) -> SkillDefinition:
    return bonus_skill_definition(skill_id, SkillKind.SERIES)


def group_skill_definition(skill_id: str) -> SkillDefinition:
    return bonus_skill_definition(skill_id, SkillKind.GROUP)


def normal_skill_definition(skill_id: str, kind: SkillKind) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=(SkillRankDefinition(level=1, required_pieces=None),),
    )


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition()


def skill_definition_generator() -> Iterator[SkillDefinition]:
    yield series_skill_definition("skill:series-a")


class EquipmentTuple(tuple):
    pass


class SkillDefinitionTuple(tuple):
    pass


def expand(
    *,
    equipment: tuple[EquipmentDefinition, ...] = (),
    skill_definitions: tuple[SkillDefinition, ...] = (),
) -> tuple[EquipmentDefinition, ...]:
    return expand_equipment_bonus_skill_variants(
        equipment=equipment,
        skill_definitions=skill_definitions,
    )


def membership_pairs(
    equipment: tuple[EquipmentDefinition, ...],
) -> tuple[tuple[str | None, str | None], ...]:
    return tuple(
        (definition.series_skill_id, definition.group_skill_id)
        for definition in equipment
    )


def test_empty_inputs_return_empty_tuple() -> None:
    result = expand()

    assert type(result) is tuple
    assert result == ()


def test_nonassignable_items_are_returned_unchanged_in_input_order() -> None:
    first = equipment_definition("equipment:weapon:first")
    second = equipment_definition(
        "equipment:weapon:second",
        series_skill_id="skill:fixed-series",
        group_skill_id="skill:fixed-group",
    )

    result = expand(equipment=(first, second))

    assert result == (first, second)
    assert result[0] is first
    assert result[1] is second


def test_series_only_assignment_expands_in_definition_order() -> None:
    template = equipment_definition(allows_series_skill_assignment=True)

    result = expand(
        equipment=(template,),
        skill_definitions=(
            series_skill_definition("skill:series-a"),
            series_skill_definition("skill:series-b"),
        ),
    )

    assert membership_pairs(result) == (
        ("skill:series-a", None),
        ("skill:series-b", None),
    )


def test_group_only_assignment_expands_in_definition_order() -> None:
    template = equipment_definition(allows_group_skill_assignment=True)

    result = expand(
        equipment=(template,),
        skill_definitions=(
            group_skill_definition("skill:group-a"),
            group_skill_definition("skill:group-b"),
        ),
    )

    assert membership_pairs(result) == (
        (None, "skill:group-a"),
        (None, "skill:group-b"),
    )


def test_dual_assignment_expands_cartesian_product_in_exact_order() -> None:
    template = equipment_definition(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )

    result = expand(
        equipment=(template,),
        skill_definitions=(
            group_skill_definition("skill:group-a"),
            series_skill_definition("skill:series-a"),
            group_skill_definition("skill:group-b"),
            series_skill_definition("skill:series-b"),
        ),
    )

    assert len(result) == 4
    assert membership_pairs(result) == (
        ("skill:series-a", "skill:group-a"),
        ("skill:series-a", "skill:group-b"),
        ("skill:series-b", "skill:group-a"),
        ("skill:series-b", "skill:group-b"),
    )


def test_normal_skill_definitions_are_ignored_as_assignment_options() -> None:
    template = equipment_definition(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )

    result = expand(
        equipment=(template,),
        skill_definitions=(
            normal_skill_definition("skill:armor", SkillKind.ARMOR),
            series_skill_definition("skill:series"),
            normal_skill_definition("skill:weapon", SkillKind.WEAPON),
            group_skill_definition("skill:group"),
        ),
    )

    assert membership_pairs(result) == (("skill:series", "skill:group"),)


def test_disabled_category_preserves_fixed_membership() -> None:
    series_template = equipment_definition(
        "equipment:weapon:series-template",
        group_skill_id="skill:fixed-group",
        allows_series_skill_assignment=True,
    )
    group_template = equipment_definition(
        "equipment:weapon:group-template",
        series_skill_id="skill:fixed-series",
        allows_group_skill_assignment=True,
    )

    result = expand(
        equipment=(series_template, group_template),
        skill_definitions=(
            series_skill_definition("skill:series-option"),
            group_skill_definition("skill:group-option"),
        ),
    )

    assert membership_pairs(result) == (
        ("skill:series-option", "skill:fixed-group"),
        ("skill:fixed-series", "skill:group-option"),
    )


def test_generated_variants_clear_assignment_flags() -> None:
    template = equipment_definition(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )

    result = expand(
        equipment=(template,),
        skill_definitions=(
            series_skill_definition("skill:series"),
            group_skill_definition("skill:group"),
        ),
    )

    assert result[0].allows_series_skill_assignment is False
    assert result[0].allows_group_skill_assignment is False


def test_generated_variants_preserve_base_equipment_fields() -> None:
    template = equipment_definition(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )

    result = expand(
        equipment=(template,),
        skill_definitions=(
            series_skill_definition("skill:series"),
            group_skill_definition("skill:group"),
        ),
    )
    generated = result[0]

    assert generated is not template
    assert generated.equipment_id == template.equipment_id
    assert generated.part is template.part
    assert generated.skills == template.skills
    assert generated.slots == template.slots


def test_generated_variants_keep_duplicate_output_equipment_ids() -> None:
    template = equipment_definition(allows_series_skill_assignment=True)

    result = expand(
        equipment=(template,),
        skill_definitions=(
            series_skill_definition("skill:series-a"),
            series_skill_definition("skill:series-b"),
        ),
    )

    assert [definition.equipment_id for definition in result] == [
        template.equipment_id,
        template.equipment_id,
    ]


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
def test_enabled_category_requires_matching_skill_option(field_name: str) -> None:
    assignments = {field_name: True}
    template = EquipmentDefinition(
        equipment_id="equipment:weapon:artian",
        part=EquipmentPart.WEAPON,
        skills=(),
        slots=(),
        **assignments,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError) as exc_info:
        expand(equipment=(template,), skill_definitions=())

    assert "skill_definitions" in str(exc_info.value)
    assert field_name in str(exc_info.value)


@pytest.mark.parametrize(
    "equipment",
    [[equipment_definition()], {equipment_definition()}, equipment_generator(), None],
)
def test_rejects_non_tuple_equipment(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        expand_equipment_bonus_skill_variants(
            equipment=equipment,  # type: ignore[arg-type]
            skill_definitions=(),
        )


def test_rejects_equipment_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="equipment"):
        expand(equipment=EquipmentTuple((equipment_definition(),)))


@pytest.mark.parametrize("invalid_equipment", ["equipment", None, 1])
def test_rejects_invalid_equipment_elements(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        expand(equipment=(invalid_equipment,))  # type: ignore[arg-type]


def test_rejects_duplicate_input_equipment_ids() -> None:
    with pytest.raises(ValueError, match="equipment"):
        expand(
            equipment=(
                equipment_definition("equipment:duplicate"),
                equipment_definition("equipment:duplicate"),
            )
        )


@pytest.mark.parametrize(
    "skill_definitions",
    [
        [series_skill_definition("skill:series")],
        {series_skill_definition("skill:series")},
        skill_definition_generator(),
        None,
    ],
)
def test_rejects_non_tuple_skill_definitions(skill_definitions: object) -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        expand_equipment_bonus_skill_variants(
            equipment=(),
            skill_definitions=skill_definitions,  # type: ignore[arg-type]
        )


def test_rejects_skill_definitions_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        expand(
            skill_definitions=SkillDefinitionTuple(
                (series_skill_definition("skill:series"),)
            )
        )


@pytest.mark.parametrize("invalid_definition", ["skill", None, 1])
def test_rejects_invalid_skill_definition_elements(
    invalid_definition: object,
) -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        expand(
            skill_definitions=(invalid_definition,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_skill_definition_ids() -> None:
    with pytest.raises(ValueError, match="skill_definitions"):
        expand(
            skill_definitions=(
                series_skill_definition("skill:duplicate"),
                group_skill_definition("skill:duplicate"),
            )
        )


def test_inputs_are_not_modified() -> None:
    template = equipment_definition(allows_series_skill_assignment=True)
    equipment = (template,)
    skill_definitions = (series_skill_definition("skill:series"),)

    expand(equipment=equipment, skill_definitions=skill_definitions)

    assert equipment == (template,)
    assert template.series_skill_id is None
    assert template.allows_series_skill_assignment is True
    assert skill_definitions == (series_skill_definition("skill:series"),)


def test_each_call_returns_a_new_outer_tuple() -> None:
    equipment = (equipment_definition(),)

    first = expand(equipment=equipment)
    second = expand(equipment=equipment)

    assert first == second
    assert first is not second


def test_function_requires_keyword_arguments() -> None:
    signature = inspect.signature(expand_equipment_bonus_skill_variants)

    assert signature.parameters["equipment"].kind is inspect.Parameter.KEYWORD_ONLY
    assert (
        signature.parameters["skill_definitions"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    with pytest.raises(TypeError):
        expand_equipment_bonus_skill_variants((), ())  # type: ignore[misc]


def test_solver_package_exports_variant_expansion() -> None:
    from mhwilds_skill_sim.solver import (
        expand_equipment_bonus_skill_variants as exported_expansion,
    )

    assert exported_expansion is expand_equipment_bonus_skill_variants
