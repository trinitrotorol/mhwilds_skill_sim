from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.validation import (
    DecorationPlacement,
    DecorationPlacementIssueCode,
    EquipmentSelectionIssueCode,
)
from mhwilds_skill_sim.validation.build import BuildValidationResult, validate_build
from mhwilds_skill_sim.validation.equipment_selection import (
    EquipmentSelectionIssue,
    validate_equipment_selection,
)
from mhwilds_skill_sim.validation.placement_validation import (
    DecorationPlacementIssue,
    validate_decoration_placements,
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


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def equipment_definition(
    part: EquipmentPart = EquipmentPart.WEAPON,
    *,
    equipment_id: str | None = None,
    slots: tuple[DecorationSlot, ...] | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=(skill(),),
        slots=slots if slots is not None else (),
    )


def complete_equipment(
    *,
    weapon_slots: tuple[DecorationSlot, ...] | None = None,
) -> tuple[EquipmentDefinition, ...]:
    return tuple(
        equipment_definition(
            part,
            slots=weapon_slots if part is EquipmentPart.WEAPON else (),
        )
        for part in REQUIRED_PARTS
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


def equipment_issue(
    code: EquipmentSelectionIssueCode,
    part: EquipmentPart,
    equipment_index: int | None,
) -> EquipmentSelectionIssue:
    return EquipmentSelectionIssue(
        code=code,
        part=part,
        equipment_index=equipment_index,
    )


def decoration_issue(
    placement_index: int,
    code: DecorationPlacementIssueCode,
) -> DecorationPlacementIssue:
    return DecorationPlacementIssue(
        placement_index=placement_index,
        code=code,
    )


def equipment_selection_issue_generator() -> Iterator[EquipmentSelectionIssue]:
    yield equipment_issue(
        EquipmentSelectionIssueCode.MISSING_PART,
        EquipmentPart.CHARM,
        None,
    )


def decoration_placement_issue_generator() -> Iterator[DecorationPlacementIssue]:
    yield decoration_issue(
        0,
        DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT,
    )


class EquipmentSelectionIssueTuple(tuple):
    pass


class DecorationPlacementIssueTuple(tuple):
    pass


def test_can_create_build_validation_result_with_empty_issues() -> None:
    result = BuildValidationResult(
        equipment_selection_issues=(),
        decoration_placement_issues=(),
    )

    assert result.equipment_selection_issues == ()
    assert result.decoration_placement_issues == ()


def test_build_validation_result_keeps_equipment_selection_issues() -> None:
    equipment_issues = (
        equipment_issue(
            EquipmentSelectionIssueCode.MISSING_PART,
            EquipmentPart.HEAD,
            None,
        ),
    )

    result = BuildValidationResult(
        equipment_selection_issues=equipment_issues,
        decoration_placement_issues=(),
    )

    assert result.equipment_selection_issues == equipment_issues


def test_build_validation_result_keeps_decoration_placement_issues() -> None:
    decoration_issues = (
        decoration_issue(
            0,
            DecorationPlacementIssueCode.UNKNOWN_DECORATION,
        ),
    )

    result = BuildValidationResult(
        equipment_selection_issues=(),
        decoration_placement_issues=decoration_issues,
    )

    assert result.decoration_placement_issues == decoration_issues


def test_build_validation_results_with_same_values_are_equal() -> None:
    assert BuildValidationResult((), ()) == BuildValidationResult((), ())


def test_build_validation_result_is_hashable() -> None:
    assert hash(BuildValidationResult((), ())) == hash(BuildValidationResult((), ()))


def test_build_validation_result_fields_cannot_be_reassigned() -> None:
    result = BuildValidationResult((), ())

    with pytest.raises(FrozenInstanceError):
        result.equipment_selection_issues = ()


@pytest.mark.parametrize(
    "equipment_selection_issues",
    [
        [],
        set(),
        equipment_selection_issue_generator(),
        None,
        EquipmentSelectionIssueTuple(),
    ],
)
def test_rejects_invalid_equipment_selection_issue_tuple(
    equipment_selection_issues: object,
) -> None:
    with pytest.raises(TypeError, match="equipment_selection_issues"):
        BuildValidationResult(
            equipment_selection_issues=equipment_selection_issues,  # type: ignore[arg-type]
            decoration_placement_issues=(),
        )


@pytest.mark.parametrize("invalid_issue", ["issue", None])
def test_rejects_invalid_equipment_selection_issue_elements(
    invalid_issue: object,
) -> None:
    with pytest.raises(TypeError, match="equipment_selection_issues"):
        BuildValidationResult(
            equipment_selection_issues=(invalid_issue,),  # type: ignore[arg-type]
            decoration_placement_issues=(),
        )


@pytest.mark.parametrize(
    "decoration_placement_issues",
    [
        [],
        set(),
        decoration_placement_issue_generator(),
        None,
        DecorationPlacementIssueTuple(),
    ],
)
def test_rejects_invalid_decoration_placement_issue_tuple(
    decoration_placement_issues: object,
) -> None:
    with pytest.raises(TypeError, match="decoration_placement_issues"):
        BuildValidationResult(
            equipment_selection_issues=(),
            decoration_placement_issues=decoration_placement_issues,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_issue", ["issue", None])
def test_rejects_invalid_decoration_placement_issue_elements(
    invalid_issue: object,
) -> None:
    with pytest.raises(TypeError, match="decoration_placement_issues"):
        BuildValidationResult(
            equipment_selection_issues=(),
            decoration_placement_issues=(invalid_issue,),  # type: ignore[arg-type]
        )


def test_validate_build_with_complete_equipment_and_no_placements_has_no_issues() -> (
    None
):
    result = validate_build(
        equipment=complete_equipment(),
        decorations=(),
        placements=(),
    )

    assert result == BuildValidationResult((), ())


def test_validate_build_with_valid_decoration_placement_has_no_issues() -> None:
    result = validate_build(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(decoration_definition(required_slot=weapon_slot(1)),),
        placements=(placement(),),
    )

    assert result == BuildValidationResult((), ())


def test_validate_build_returns_build_validation_result() -> None:
    result = validate_build(
        equipment=complete_equipment(),
        decorations=(),
        placements=(),
    )

    assert isinstance(result, BuildValidationResult)


def test_validate_build_requires_keyword_arguments() -> None:
    with pytest.raises(TypeError):
        validate_build(complete_equipment(), (), ())  # type: ignore[misc]


def test_validation_package_exports_build_validation_facade() -> None:
    from mhwilds_skill_sim.validation import (
        BuildValidationResult as ExportedBuildValidationResult,
        validate_build as exported_validate_build,
    )

    assert ExportedBuildValidationResult is BuildValidationResult
    assert exported_validate_build is validate_build


def test_validation_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.validation import (
        DecorationPlacement as ExportedDecorationPlacement,
        DecorationPlacementIssue as ExportedDecorationPlacementIssue,
        DecorationPlacementIssueCode as ExportedDecorationPlacementIssueCode,
        EquipmentSelectionIssue as ExportedEquipmentSelectionIssue,
        EquipmentSelectionIssueCode as ExportedEquipmentSelectionIssueCode,
        can_place_decoration_in_equipment_slot as exported_slot_validator,
        validate_decoration_placements as exported_placement_validator,
        validate_equipment_selection as exported_equipment_validator,
    )
    from mhwilds_skill_sim.validation.decoration import (
        can_place_decoration_in_equipment_slot,
    )

    assert ExportedDecorationPlacement is DecorationPlacement
    assert ExportedDecorationPlacementIssue is DecorationPlacementIssue
    assert ExportedDecorationPlacementIssueCode is DecorationPlacementIssueCode
    assert ExportedEquipmentSelectionIssue is EquipmentSelectionIssue
    assert ExportedEquipmentSelectionIssueCode is EquipmentSelectionIssueCode
    assert exported_slot_validator is can_place_decoration_in_equipment_slot
    assert exported_placement_validator is validate_decoration_placements
    assert exported_equipment_validator is validate_equipment_selection


def test_validate_build_aggregates_missing_equipment_part_issues() -> None:
    result = validate_build(
        equipment=(),
        decorations=(),
        placements=(),
    )

    assert result.equipment_selection_issues == tuple(
        equipment_issue(EquipmentSelectionIssueCode.MISSING_PART, part, None)
        for part in REQUIRED_PARTS
    )
    assert result.decoration_placement_issues == ()


def test_validate_build_aggregates_duplicate_equipment_part_issues() -> None:
    equipment = (
        equipment_definition(EquipmentPart.WEAPON, equipment_id="equipment:weapon-a"),
        equipment_definition(EquipmentPart.WEAPON, equipment_id="equipment:weapon-b"),
        *(equipment_definition(part) for part in REQUIRED_PARTS[1:]),
    )

    result = validate_build(equipment=equipment, decorations=(), placements=())

    assert result.equipment_selection_issues == (
        equipment_issue(
            EquipmentSelectionIssueCode.DUPLICATE_PART,
            EquipmentPart.WEAPON,
            1,
        ),
    )


def test_validate_build_aggregates_unknown_equipment_placement_issues() -> None:
    result = validate_build(
        equipment=complete_equipment(),
        decorations=(decoration_definition(),),
        placements=(placement("equipment:unknown", 0, "decoration:weapon-1"),),
    )

    assert result.decoration_placement_issues == (
        decoration_issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT),
    )


def test_validate_build_aggregates_unknown_decoration_placement_issues() -> None:
    result = validate_build(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(),
        placements=(placement("equipment:weapon", 0, "decoration:unknown"),),
    )

    assert result.decoration_placement_issues == (
        decoration_issue(0, DecorationPlacementIssueCode.UNKNOWN_DECORATION),
    )


def test_validate_build_aggregates_invalid_slot_index_issues() -> None:
    result = validate_build(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(decoration_definition(),),
        placements=(placement("equipment:weapon", 1, "decoration:weapon-1"),),
    )

    assert result.decoration_placement_issues == (
        decoration_issue(0, DecorationPlacementIssueCode.INVALID_SLOT_INDEX),
    )


def test_validate_build_aggregates_duplicate_slot_issues() -> None:
    result = validate_build(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(
            decoration_definition("decoration:weapon-a"),
            decoration_definition("decoration:weapon-b"),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:weapon-a"),
            placement("equipment:weapon", 0, "decoration:weapon-b"),
        ),
    )

    assert result.decoration_placement_issues == (
        decoration_issue(1, DecorationPlacementIssueCode.DUPLICATE_SLOT),
    )


def test_validate_build_aggregates_incompatible_slot_issues() -> None:
    result = validate_build(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(decoration_definition(required_slot=armor_slot(1)),),
        placements=(placement(),),
    )

    assert result.decoration_placement_issues == (
        decoration_issue(0, DecorationPlacementIssueCode.INCOMPATIBLE_SLOT),
    )


def test_validate_build_returns_placement_issues_when_equipment_issues_exist() -> None:
    result = validate_build(
        equipment=(equipment_definition(EquipmentPart.WEAPON),),
        decorations=(),
        placements=(placement("equipment:unknown", 0, "decoration:unknown"),),
    )

    assert result.equipment_selection_issues
    assert result.decoration_placement_issues == (
        decoration_issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT),
    )


def test_validate_build_preserves_each_validator_issue_order() -> None:
    result = validate_build(
        equipment=(
            equipment_definition(EquipmentPart.WEAPON, equipment_id="equipment:weapon"),
            equipment_definition(
                EquipmentPart.WEAPON,
                equipment_id="equipment:weapon-duplicate",
            ),
        ),
        decorations=(decoration_definition("decoration:weapon-1"),),
        placements=(
            placement("equipment:unknown", 0, "decoration:weapon-1"),
            placement("equipment:weapon", 0, "decoration:unknown"),
        ),
    )

    assert result.equipment_selection_issues == (
        equipment_issue(
            EquipmentSelectionIssueCode.DUPLICATE_PART,
            EquipmentPart.WEAPON,
            1,
        ),
        equipment_issue(
            EquipmentSelectionIssueCode.MISSING_PART, EquipmentPart.HEAD, None
        ),
        equipment_issue(
            EquipmentSelectionIssueCode.MISSING_PART,
            EquipmentPart.CHEST,
            None,
        ),
        equipment_issue(
            EquipmentSelectionIssueCode.MISSING_PART, EquipmentPart.ARMS, None
        ),
        equipment_issue(
            EquipmentSelectionIssueCode.MISSING_PART,
            EquipmentPart.WAIST,
            None,
        ),
        equipment_issue(
            EquipmentSelectionIssueCode.MISSING_PART, EquipmentPart.LEGS, None
        ),
        equipment_issue(
            EquipmentSelectionIssueCode.MISSING_PART,
            EquipmentPart.CHARM,
            None,
        ),
    )
    assert result.decoration_placement_issues == (
        decoration_issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT),
        decoration_issue(1, DecorationPlacementIssueCode.UNKNOWN_DECORATION),
    )


def test_validate_build_propagates_equipment_tuple_errors() -> None:
    with pytest.raises(TypeError, match="equipment"):
        validate_build(
            equipment=[],  # type: ignore[arg-type]
            decorations=(),
            placements=(),
        )


def test_validate_build_propagates_decoration_tuple_errors() -> None:
    with pytest.raises(TypeError, match="decorations"):
        validate_build(
            equipment=complete_equipment(),
            decorations=[],  # type: ignore[arg-type]
            placements=(),
        )


def test_validate_build_propagates_placement_tuple_errors() -> None:
    with pytest.raises(TypeError, match="placements"):
        validate_build(
            equipment=complete_equipment(),
            decorations=(),
            placements=[],  # type: ignore[arg-type]
        )


def test_validate_build_propagates_equipment_element_errors() -> None:
    with pytest.raises(TypeError, match="equipment"):
        validate_build(
            equipment=("equipment:weapon",),  # type: ignore[arg-type]
            decorations=(),
            placements=(),
        )


def test_validate_build_propagates_decoration_element_errors() -> None:
    with pytest.raises(TypeError, match="decorations"):
        validate_build(
            equipment=complete_equipment(),
            decorations=("decoration:weapon-1",),  # type: ignore[arg-type]
            placements=(),
        )


def test_validate_build_propagates_placement_element_errors() -> None:
    with pytest.raises(TypeError, match="placements"):
        validate_build(
            equipment=complete_equipment(),
            decorations=(),
            placements=("placement",),  # type: ignore[arg-type]
        )


def test_validate_build_propagates_duplicate_equipment_id_errors() -> None:
    equipment = (
        equipment_definition(EquipmentPart.WEAPON, equipment_id="equipment:duplicate"),
        equipment_definition(EquipmentPart.HEAD, equipment_id="equipment:duplicate"),
        *(equipment_definition(part) for part in REQUIRED_PARTS[2:]),
    )

    with pytest.raises(ValueError, match="equipment"):
        validate_build(equipment=equipment, decorations=(), placements=())


def test_validate_build_propagates_duplicate_decoration_id_errors() -> None:
    with pytest.raises(ValueError, match="decorations"):
        validate_build(
            equipment=complete_equipment(),
            decorations=(
                decoration_definition("decoration:duplicate"),
                decoration_definition("decoration:duplicate"),
            ),
            placements=(),
        )


def test_validate_build_checks_equipment_before_other_invalid_inputs() -> None:
    with pytest.raises(TypeError, match="equipment"):
        validate_build(
            equipment=[],  # type: ignore[arg-type]
            decorations=[],  # type: ignore[arg-type]
            placements=(),
        )
