from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.validation.decoration import (
    can_place_decoration_in_equipment_slot,
)
from mhwilds_skill_sim.validation.placement import DecorationPlacement
from mhwilds_skill_sim.validation.placement_validation import (
    DecorationPlacementIssue,
    DecorationPlacementIssueCode,
    validate_decoration_placements,
)


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def equipment_definition(
    equipment_id: str = "equipment:weapon",
    *,
    part: EquipmentPart = EquipmentPart.WEAPON,
    slots: tuple[DecorationSlot, ...] | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=(skill(),),
        slots=slots if slots is not None else (weapon_slot(1),),
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


def validate(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    decorations: tuple[DecorationDefinition, ...] | None = None,
    placements: tuple[DecorationPlacement, ...] = (),
) -> tuple[DecorationPlacementIssue, ...]:
    return validate_decoration_placements(
        equipment=(
            equipment
            if equipment is not None
            else (equipment_definition(slots=(weapon_slot(1),)),)
        ),
        decorations=(
            decorations
            if decorations is not None
            else (decoration_definition(required_slot=weapon_slot(1)),)
        ),
        placements=placements,
    )


def issue(
    placement_index: int,
    code: DecorationPlacementIssueCode,
) -> DecorationPlacementIssue:
    return DecorationPlacementIssue(placement_index=placement_index, code=code)


def placement_generator() -> Iterator[DecorationPlacement]:
    yield placement()


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition()


def decoration_generator() -> Iterator[DecorationDefinition]:
    yield decoration_definition()


class EquipmentTuple(tuple):
    pass


class DecorationTuple(tuple):
    pass


class PlacementTuple(tuple):
    pass


def test_issue_code_values_match_public_contract() -> None:
    assert list(DecorationPlacementIssueCode) == [
        DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT,
        DecorationPlacementIssueCode.UNKNOWN_DECORATION,
        DecorationPlacementIssueCode.INVALID_SLOT_INDEX,
        DecorationPlacementIssueCode.DUPLICATE_SLOT,
        DecorationPlacementIssueCode.INCOMPATIBLE_SLOT,
    ]
    assert [code.value for code in DecorationPlacementIssueCode] == [
        "unknown_equipment",
        "unknown_decoration",
        "invalid_slot_index",
        "duplicate_slot",
        "incompatible_slot",
    ]


def test_can_create_decoration_placement_issue() -> None:
    definition = DecorationPlacementIssue(
        placement_index=1,
        code=DecorationPlacementIssueCode.UNKNOWN_DECORATION,
    )

    assert definition.placement_index == 1
    assert definition.code is DecorationPlacementIssueCode.UNKNOWN_DECORATION


def test_decoration_placement_issues_with_same_values_are_equal() -> None:
    assert issue(1, DecorationPlacementIssueCode.INVALID_SLOT_INDEX) == issue(
        1,
        DecorationPlacementIssueCode.INVALID_SLOT_INDEX,
    )


def test_decoration_placement_issue_is_hashable() -> None:
    assert hash(issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT)) == hash(
        issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT),
    )


def test_decoration_placement_issue_fields_cannot_be_reassigned() -> None:
    definition = issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT)

    with pytest.raises(FrozenInstanceError):
        definition.code = DecorationPlacementIssueCode.UNKNOWN_DECORATION


def test_decoration_placement_issue_rejects_bool_placement_index() -> None:
    with pytest.raises(TypeError, match="placement_index"):
        DecorationPlacementIssue(
            placement_index=True,  # type: ignore[arg-type]
            code=DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT,
        )


def test_decoration_placement_issue_rejects_negative_placement_index() -> None:
    with pytest.raises(ValueError, match="placement_index"):
        DecorationPlacementIssue(
            placement_index=-1,
            code=DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT,
        )


@pytest.mark.parametrize("code", ["unknown_equipment", None])
def test_decoration_placement_issue_rejects_invalid_code(code: object) -> None:
    with pytest.raises(TypeError, match="code"):
        DecorationPlacementIssue(placement_index=0, code=code)  # type: ignore[arg-type]


def test_empty_placements_returns_empty_tuple() -> None:
    assert validate(placements=()) == ()


def test_valid_single_placement_returns_empty_tuple() -> None:
    assert validate(placements=(placement(),)) == ()


def test_valid_multiple_placements_return_empty_tuple() -> None:
    assert (
        validate(
            equipment=(
                equipment_definition(
                    "equipment:weapon",
                    slots=(weapon_slot(1), weapon_slot(2)),
                ),
                equipment_definition(
                    "equipment:head",
                    part=EquipmentPart.HEAD,
                    slots=(armor_slot(1),),
                ),
            ),
            decorations=(
                decoration_definition(
                    "decoration:weapon-1", required_slot=weapon_slot(1)
                ),
                decoration_definition(
                    "decoration:armor-1", required_slot=armor_slot(1)
                ),
            ),
            placements=(
                placement("equipment:weapon", 0, "decoration:weapon-1"),
                placement("equipment:head", 0, "decoration:armor-1"),
            ),
        )
        == ()
    )


def test_same_equipment_different_slots_are_valid() -> None:
    assert (
        validate(
            equipment=(
                equipment_definition(
                    slots=(weapon_slot(1), weapon_slot(1)),
                ),
            ),
            decorations=(
                decoration_definition(
                    "decoration:weapon-a", required_slot=weapon_slot(1)
                ),
                decoration_definition(
                    "decoration:weapon-b", required_slot=weapon_slot(1)
                ),
            ),
            placements=(
                placement("equipment:weapon", 0, "decoration:weapon-a"),
                placement("equipment:weapon", 1, "decoration:weapon-b"),
            ),
        )
        == ()
    )


def test_different_equipment_same_slot_index_is_valid() -> None:
    assert (
        validate(
            equipment=(
                equipment_definition("equipment:weapon-a", slots=(weapon_slot(1),)),
                equipment_definition("equipment:weapon-b", slots=(weapon_slot(1),)),
            ),
            decorations=(
                decoration_definition(
                    "decoration:weapon-a", required_slot=weapon_slot(1)
                ),
                decoration_definition(
                    "decoration:weapon-b", required_slot=weapon_slot(1)
                ),
            ),
            placements=(
                placement("equipment:weapon-a", 0, "decoration:weapon-a"),
                placement("equipment:weapon-b", 0, "decoration:weapon-b"),
            ),
        )
        == ()
    )


def test_identical_slots_on_same_equipment_are_valid_at_different_indexes() -> None:
    assert (
        validate(
            equipment=(equipment_definition(slots=(weapon_slot(1), weapon_slot(1))),),
            decorations=(
                decoration_definition(
                    "decoration:weapon-a", required_slot=weapon_slot(1)
                ),
                decoration_definition(
                    "decoration:weapon-b", required_slot=weapon_slot(1)
                ),
            ),
            placements=(
                placement("equipment:weapon", 0, "decoration:weapon-a"),
                placement("equipment:weapon", 1, "decoration:weapon-b"),
            ),
        )
        == ()
    )


def test_weapon_part_with_armor_slot_can_accept_armor_decoration() -> None:
    assert (
        validate(
            equipment=(
                equipment_definition(
                    part=EquipmentPart.WEAPON,
                    slots=(armor_slot(1),),
                ),
            ),
            decorations=(decoration_definition(required_slot=armor_slot(1)),),
            placements=(placement(),),
        )
        == ()
    )


def test_head_part_with_weapon_slot_can_accept_weapon_decoration() -> None:
    assert (
        validate(
            equipment=(
                equipment_definition(
                    part=EquipmentPart.HEAD,
                    slots=(weapon_slot(1),),
                ),
            ),
            decorations=(decoration_definition(required_slot=weapon_slot(1)),),
            placements=(placement(),),
        )
        == ()
    )


def test_return_value_is_tuple() -> None:
    issues = validate(
        placements=(placement("unknown:equipment", 0, "decoration:weapon-1"),)
    )

    assert type(issues) is tuple


def test_issue_order_follows_input_order() -> None:
    assert validate(
        placements=(
            placement("unknown:equipment", 0, "decoration:weapon-1"),
            placement("equipment:weapon", 0, "unknown:decoration"),
            placement("equipment:weapon", 2, "decoration:weapon-1"),
        ),
    ) == (
        issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT),
        issue(1, DecorationPlacementIssueCode.UNKNOWN_DECORATION),
        issue(2, DecorationPlacementIssueCode.INVALID_SLOT_INDEX),
    )


def test_validate_decoration_placements_requires_keyword_arguments() -> None:
    with pytest.raises(TypeError):
        validate_decoration_placements(  # type: ignore[misc]
            (equipment_definition(),),
            (decoration_definition(),),
            (),
        )


def test_validation_package_exports_public_placement_validation_types() -> None:
    from mhwilds_skill_sim.validation import (
        DecorationPlacementIssue as ExportedIssue,
        DecorationPlacementIssueCode as ExportedIssueCode,
        validate_decoration_placements as exported_validate,
    )

    assert ExportedIssue is DecorationPlacementIssue
    assert ExportedIssueCode is DecorationPlacementIssueCode
    assert exported_validate is validate_decoration_placements


def test_validation_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.validation import (
        DecorationPlacement as ExportedDecorationPlacement,
        can_place_decoration_in_equipment_slot as exported_slot_validator,
    )

    assert ExportedDecorationPlacement is DecorationPlacement
    assert exported_slot_validator is can_place_decoration_in_equipment_slot


def test_unknown_equipment_issue() -> None:
    assert validate(
        placements=(placement("unknown:equipment", 0, "decoration:weapon-1"),),
    ) == (issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT),)


def test_unknown_decoration_issue() -> None:
    assert validate(
        placements=(placement("equipment:weapon", 0, "unknown:decoration"),),
    ) == (issue(0, DecorationPlacementIssueCode.UNKNOWN_DECORATION),)


def test_invalid_slot_index_issue() -> None:
    assert validate(
        placements=(placement("equipment:weapon", 1, "decoration:weapon-1"),),
    ) == (issue(0, DecorationPlacementIssueCode.INVALID_SLOT_INDEX),)


def test_equipment_without_slots_has_invalid_slot_index_issue() -> None:
    assert validate(
        equipment=(equipment_definition(slots=()),),
        placements=(placement(),),
    ) == (issue(0, DecorationPlacementIssueCode.INVALID_SLOT_INDEX),)


def test_duplicate_slot_issue_for_second_placement() -> None:
    assert validate(
        decorations=(
            decoration_definition("decoration:weapon-a", required_slot=weapon_slot(1)),
            decoration_definition("decoration:weapon-b", required_slot=weapon_slot(1)),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:weapon-a"),
            placement("equipment:weapon", 0, "decoration:weapon-b"),
        ),
    ) == (issue(1, DecorationPlacementIssueCode.DUPLICATE_SLOT),)


@pytest.mark.parametrize(
    ("required_slot", "available_slot"),
    [
        (weapon_slot(1), armor_slot(1)),
        (armor_slot(1), weapon_slot(1)),
        (weapon_slot(2), weapon_slot(1)),
    ],
)
def test_incompatible_slot_issue(
    required_slot: DecorationSlot,
    available_slot: DecorationSlot,
) -> None:
    assert validate(
        equipment=(equipment_definition(slots=(available_slot,)),),
        decorations=(decoration_definition(required_slot=required_slot),),
        placements=(placement(),),
    ) == (issue(0, DecorationPlacementIssueCode.INCOMPATIBLE_SLOT),)


def test_invalid_placement_does_not_reserve_slot() -> None:
    assert validate(
        equipment=(equipment_definition(slots=(weapon_slot(1),)),),
        decorations=(
            decoration_definition("decoration:armor", required_slot=armor_slot(1)),
            decoration_definition("decoration:weapon", required_slot=weapon_slot(1)),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:armor"),
            placement("equipment:weapon", 0, "decoration:weapon"),
        ),
    ) == (issue(0, DecorationPlacementIssueCode.INCOMPATIBLE_SLOT),)


def test_only_valid_placement_reserves_slot() -> None:
    assert validate(
        decorations=(
            decoration_definition("decoration:weapon-a", required_slot=weapon_slot(1)),
            decoration_definition("decoration:weapon-b", required_slot=weapon_slot(1)),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:weapon-a"),
            placement("equipment:weapon", 0, "decoration:weapon-b"),
        ),
    ) == (issue(1, DecorationPlacementIssueCode.DUPLICATE_SLOT),)


def test_unknown_equipment_has_priority_over_unknown_decoration() -> None:
    assert validate(
        placements=(placement("unknown:equipment", 0, "unknown:decoration"),),
    ) == (issue(0, DecorationPlacementIssueCode.UNKNOWN_EQUIPMENT),)


def test_unknown_decoration_has_priority_over_invalid_slot_index() -> None:
    assert validate(
        placements=(placement("equipment:weapon", 1, "unknown:decoration"),),
    ) == (issue(0, DecorationPlacementIssueCode.UNKNOWN_DECORATION),)


def test_invalid_slot_index_has_priority_over_duplicate_candidate() -> None:
    assert validate(
        equipment=(equipment_definition(slots=(weapon_slot(1),)),),
        decorations=(
            decoration_definition("decoration:weapon-a", required_slot=weapon_slot(1)),
            decoration_definition("decoration:weapon-b", required_slot=weapon_slot(1)),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:weapon-a"),
            placement("equipment:weapon", 1, "decoration:weapon-b"),
        ),
    ) == (issue(1, DecorationPlacementIssueCode.INVALID_SLOT_INDEX),)


def test_duplicate_slot_has_priority_over_incompatible_slot() -> None:
    assert validate(
        equipment=(equipment_definition(slots=(weapon_slot(1),)),),
        decorations=(
            decoration_definition("decoration:weapon", required_slot=weapon_slot(1)),
            decoration_definition("decoration:armor", required_slot=armor_slot(1)),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:weapon"),
            placement("equipment:weapon", 0, "decoration:armor"),
        ),
    ) == (issue(1, DecorationPlacementIssueCode.DUPLICATE_SLOT),)


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
        validate_decoration_placements(
            equipment=equipment,  # type: ignore[arg-type]
            decorations=(decoration_definition(),),
            placements=(),
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
        validate_decoration_placements(
            equipment=(equipment_definition(),),
            decorations=decorations,  # type: ignore[arg-type]
            placements=(),
        )


@pytest.mark.parametrize(
    "placements",
    [
        [placement()],
        {placement()},
        placement_generator(),
        None,
        PlacementTuple((placement(),)),
    ],
)
def test_rejects_non_tuple_placements(placements: object) -> None:
    with pytest.raises(TypeError, match="placements"):
        validate_decoration_placements(
            equipment=(equipment_definition(),),
            decorations=(decoration_definition(),),
            placements=placements,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_equipment", ["equipment:weapon", None])
def test_rejects_invalid_equipment_elements(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        validate_decoration_placements(
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
            decorations=(decoration_definition(),),
            placements=(),
        )


@pytest.mark.parametrize("invalid_decoration", ["decoration:weapon", None])
def test_rejects_invalid_decoration_elements(invalid_decoration: object) -> None:
    with pytest.raises(TypeError, match="decorations"):
        validate_decoration_placements(
            equipment=(equipment_definition(),),
            decorations=(invalid_decoration,),  # type: ignore[arg-type]
            placements=(),
        )


@pytest.mark.parametrize("invalid_placement", ["placement", None])
def test_rejects_invalid_placement_elements(invalid_placement: object) -> None:
    with pytest.raises(TypeError, match="placements"):
        validate_decoration_placements(
            equipment=(equipment_definition(),),
            decorations=(decoration_definition(),),
            placements=(invalid_placement,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_equipment_id() -> None:
    with pytest.raises(ValueError, match="equipment"):
        validate_decoration_placements(
            equipment=(
                equipment_definition("equipment:duplicate"),
                equipment_definition("equipment:duplicate"),
            ),
            decorations=(decoration_definition(),),
            placements=(),
        )


def test_rejects_duplicate_decoration_id() -> None:
    with pytest.raises(ValueError, match="decorations"):
        validate_decoration_placements(
            equipment=(equipment_definition(),),
            decorations=(
                decoration_definition("decoration:duplicate"),
                decoration_definition("decoration:duplicate"),
            ),
            placements=(),
        )
