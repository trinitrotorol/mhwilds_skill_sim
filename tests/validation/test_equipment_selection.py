from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.validation import (
    DecorationPlacement,
    DecorationPlacementIssue,
    DecorationPlacementIssueCode,
    can_place_decoration_in_equipment_slot,
    validate_decoration_placements,
)
from mhwilds_skill_sim.validation.equipment_selection import (
    EquipmentSelectionIssue,
    EquipmentSelectionIssueCode,
    validate_equipment_selection,
)


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
    part: EquipmentPart = EquipmentPart.WEAPON,
    *,
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


def issue(
    code: EquipmentSelectionIssueCode,
    part: EquipmentPart,
    equipment_index: int | None,
) -> EquipmentSelectionIssue:
    return EquipmentSelectionIssue(
        code=code,
        part=part,
        equipment_index=equipment_index,
    )


def missing_issue(part: EquipmentPart) -> EquipmentSelectionIssue:
    return issue(EquipmentSelectionIssueCode.MISSING_PART, part, None)


def duplicate_issue(
    part: EquipmentPart,
    equipment_index: int,
) -> EquipmentSelectionIssue:
    return issue(EquipmentSelectionIssueCode.DUPLICATE_PART, part, equipment_index)


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition()


class EquipmentTuple(tuple):
    pass


def test_issue_code_values_match_public_contract() -> None:
    assert list(EquipmentSelectionIssueCode) == [
        EquipmentSelectionIssueCode.MISSING_PART,
        EquipmentSelectionIssueCode.DUPLICATE_PART,
    ]
    assert [code.value for code in EquipmentSelectionIssueCode] == [
        "missing_part",
        "duplicate_part",
    ]


def test_can_create_missing_part_issue() -> None:
    definition = EquipmentSelectionIssue(
        code=EquipmentSelectionIssueCode.MISSING_PART,
        part=EquipmentPart.HEAD,
        equipment_index=None,
    )

    assert definition.code is EquipmentSelectionIssueCode.MISSING_PART
    assert definition.part is EquipmentPart.HEAD
    assert definition.equipment_index is None


def test_can_create_duplicate_part_issue() -> None:
    definition = EquipmentSelectionIssue(
        code=EquipmentSelectionIssueCode.DUPLICATE_PART,
        part=EquipmentPart.WEAPON,
        equipment_index=1,
    )

    assert definition.code is EquipmentSelectionIssueCode.DUPLICATE_PART
    assert definition.part is EquipmentPart.WEAPON
    assert definition.equipment_index == 1


def test_equipment_selection_issues_with_same_values_are_equal() -> None:
    assert missing_issue(EquipmentPart.CHEST) == missing_issue(EquipmentPart.CHEST)


def test_equipment_selection_issue_is_hashable() -> None:
    assert hash(duplicate_issue(EquipmentPart.WEAPON, 1)) == hash(
        duplicate_issue(EquipmentPart.WEAPON, 1),
    )


def test_equipment_selection_issue_fields_cannot_be_reassigned() -> None:
    definition = missing_issue(EquipmentPart.CHARM)

    with pytest.raises(FrozenInstanceError):
        definition.part = EquipmentPart.WEAPON


@pytest.mark.parametrize("code", ["missing_part", None])
def test_equipment_selection_issue_rejects_invalid_code(code: object) -> None:
    with pytest.raises(TypeError, match="code"):
        EquipmentSelectionIssue(
            code=code,  # type: ignore[arg-type]
            part=EquipmentPart.WEAPON,
            equipment_index=None,
        )


@pytest.mark.parametrize("part", ["weapon", None])
def test_equipment_selection_issue_rejects_invalid_part(part: object) -> None:
    with pytest.raises(TypeError, match="part"):
        EquipmentSelectionIssue(
            code=EquipmentSelectionIssueCode.MISSING_PART,
            part=part,  # type: ignore[arg-type]
            equipment_index=None,
        )


def test_equipment_selection_issue_rejects_bool_equipment_index() -> None:
    with pytest.raises(TypeError, match="equipment_index"):
        EquipmentSelectionIssue(
            code=EquipmentSelectionIssueCode.DUPLICATE_PART,
            part=EquipmentPart.WEAPON,
            equipment_index=True,  # type: ignore[arg-type]
        )


def test_equipment_selection_issue_rejects_negative_equipment_index() -> None:
    with pytest.raises(ValueError, match="equipment_index"):
        EquipmentSelectionIssue(
            code=EquipmentSelectionIssueCode.DUPLICATE_PART,
            part=EquipmentPart.WEAPON,
            equipment_index=-1,
        )


def test_missing_part_issue_rejects_int_equipment_index() -> None:
    with pytest.raises(ValueError, match="equipment_index"):
        EquipmentSelectionIssue(
            code=EquipmentSelectionIssueCode.MISSING_PART,
            part=EquipmentPart.WEAPON,
            equipment_index=0,
        )


def test_duplicate_part_issue_rejects_none_equipment_index() -> None:
    with pytest.raises(ValueError, match="equipment_index"):
        EquipmentSelectionIssue(
            code=EquipmentSelectionIssueCode.DUPLICATE_PART,
            part=EquipmentPart.WEAPON,
            equipment_index=None,
        )


def test_complete_equipment_selection_returns_empty_tuple() -> None:
    assert validate_equipment_selection(equipment=complete_equipment()) == ()


def test_complete_equipment_selection_accepts_any_input_order() -> None:
    assert (
        validate_equipment_selection(
            equipment=(
                equipment_definition(EquipmentPart.CHARM),
                equipment_definition(EquipmentPart.LEGS),
                equipment_definition(EquipmentPart.WAIST),
                equipment_definition(EquipmentPart.ARMS),
                equipment_definition(EquipmentPart.CHEST),
                equipment_definition(EquipmentPart.HEAD),
                equipment_definition(EquipmentPart.WEAPON),
            ),
        )
        == ()
    )


def test_return_value_is_tuple() -> None:
    issues = validate_equipment_selection(equipment=())

    assert type(issues) is tuple


def test_validate_equipment_selection_requires_keyword_arguments() -> None:
    with pytest.raises(TypeError):
        validate_equipment_selection(complete_equipment())  # type: ignore[misc]


def test_validation_package_exports_equipment_selection_types() -> None:
    from mhwilds_skill_sim.validation import (
        EquipmentSelectionIssue as ExportedIssue,
        EquipmentSelectionIssueCode as ExportedIssueCode,
        validate_equipment_selection as exported_validate,
    )

    assert ExportedIssue is EquipmentSelectionIssue
    assert ExportedIssueCode is EquipmentSelectionIssueCode
    assert exported_validate is validate_equipment_selection


def test_validation_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.validation import (
        DecorationPlacement as ExportedDecorationPlacement,
        DecorationPlacementIssue as ExportedDecorationPlacementIssue,
        DecorationPlacementIssueCode as ExportedDecorationPlacementIssueCode,
        can_place_decoration_in_equipment_slot as exported_slot_validator,
        validate_decoration_placements as exported_placement_validator,
    )

    assert ExportedDecorationPlacement is DecorationPlacement
    assert ExportedDecorationPlacementIssue is DecorationPlacementIssue
    assert ExportedDecorationPlacementIssueCode is DecorationPlacementIssueCode
    assert exported_slot_validator is can_place_decoration_in_equipment_slot
    assert exported_placement_validator is validate_decoration_placements


def test_empty_equipment_returns_all_missing_parts() -> None:
    assert validate_equipment_selection(equipment=()) == tuple(
        missing_issue(part) for part in REQUIRED_PARTS
    )


def test_weapon_only_returns_other_parts_missing() -> None:
    assert validate_equipment_selection(
        equipment=(equipment_definition(EquipmentPart.WEAPON),),
    ) == tuple(missing_issue(part) for part in REQUIRED_PARTS[1:])


def test_missing_charm_returns_charm_issue() -> None:
    equipment = tuple(
        equipment_definition(part)
        for part in REQUIRED_PARTS
        if part is not EquipmentPart.CHARM
    )

    assert validate_equipment_selection(equipment=equipment) == (
        missing_issue(EquipmentPart.CHARM),
    )


def test_missing_head_and_legs_returns_two_missing_issues() -> None:
    equipment = tuple(
        equipment_definition(part)
        for part in REQUIRED_PARTS
        if part not in {EquipmentPart.HEAD, EquipmentPart.LEGS}
    )

    assert validate_equipment_selection(equipment=equipment) == (
        missing_issue(EquipmentPart.HEAD),
        missing_issue(EquipmentPart.LEGS),
    )


def test_missing_issue_equipment_index_is_none() -> None:
    issues = validate_equipment_selection(equipment=())

    assert all(definition.equipment_index is None for definition in issues)


def test_missing_issue_order_follows_equipment_part_declaration_order() -> None:
    issues = validate_equipment_selection(equipment=())

    assert [definition.part for definition in issues] == list(REQUIRED_PARTS)


def test_duplicate_weapon_reports_second_weapon_index() -> None:
    assert validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:a"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:b"),
            *(equipment_definition(part) for part in REQUIRED_PARTS[1:]),
        ),
    ) == (duplicate_issue(EquipmentPart.WEAPON, 1),)


def test_three_weapons_report_second_and_third_weapon_indexes() -> None:
    assert validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:a"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:b"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:c"),
            *(equipment_definition(part) for part in REQUIRED_PARTS[1:]),
        ),
    ) == (
        duplicate_issue(EquipmentPart.WEAPON, 1),
        duplicate_issue(EquipmentPart.WEAPON, 2),
    )


def test_duplicate_head_reports_second_head_index() -> None:
    assert validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON),
            equipment_definition(EquipmentPart.HEAD, equipment_id="head:a"),
            equipment_definition(EquipmentPart.HEAD, equipment_id="head:b"),
            *(equipment_definition(part) for part in REQUIRED_PARTS[2:]),
        ),
    ) == (duplicate_issue(EquipmentPart.HEAD, 2),)


def test_multiple_duplicate_parts_are_reported_in_input_order() -> None:
    assert validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:a"),
            equipment_definition(EquipmentPart.HEAD, equipment_id="head:a"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:b"),
            equipment_definition(EquipmentPart.HEAD, equipment_id="head:b"),
            *(equipment_definition(part) for part in REQUIRED_PARTS[2:]),
        ),
    ) == (
        duplicate_issue(EquipmentPart.WEAPON, 2),
        duplicate_issue(EquipmentPart.HEAD, 3),
    )


def test_duplicate_issue_records_duplicate_equipment_index_and_part() -> None:
    issues = validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:a"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:b"),
        ),
    )

    assert issues[0].equipment_index == 1
    assert issues[0].part is EquipmentPart.WEAPON


def test_duplicate_issues_are_returned_before_missing_issues() -> None:
    assert validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:a"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:b"),
        ),
    ) == (
        duplicate_issue(EquipmentPart.WEAPON, 1),
        missing_issue(EquipmentPart.HEAD),
        missing_issue(EquipmentPart.CHEST),
        missing_issue(EquipmentPart.ARMS),
        missing_issue(EquipmentPart.WAIST),
        missing_issue(EquipmentPart.LEGS),
        missing_issue(EquipmentPart.CHARM),
    )


def test_duplicate_and_missing_keeps_missing_parts_in_declaration_order() -> None:
    issues = validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:a"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:b"),
            equipment_definition(EquipmentPart.LEGS),
        ),
    )

    assert issues[1:] == (
        missing_issue(EquipmentPart.HEAD),
        missing_issue(EquipmentPart.CHEST),
        missing_issue(EquipmentPart.ARMS),
        missing_issue(EquipmentPart.WAIST),
        missing_issue(EquipmentPart.CHARM),
    )


def test_duplicate_part_is_not_reported_as_missing() -> None:
    issues = validate_equipment_selection(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:a"),
            equipment_definition(EquipmentPart.WEAPON, equipment_id="weapon:b"),
        ),
    )

    assert missing_issue(EquipmentPart.WEAPON) not in issues


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_definition()],
        {equipment_definition()},
        equipment_generator(),
        None,
        EquipmentTuple((equipment_definition(),)),
    ],
)
def test_rejects_non_tuple_equipment(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        validate_equipment_selection(equipment=equipment)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_equipment", ["equipment:weapon", None])
def test_rejects_invalid_equipment_elements(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        validate_equipment_selection(
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
        )
