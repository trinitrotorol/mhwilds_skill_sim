from __future__ import annotations

import inspect

import pytest

from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot
from mhwilds_skill_sim.validation import (
    BuildValidationResult,
    DecorationPlacement,
    DecorationPlacementIssue,
    DecorationPlacementIssueCode,
    EquipmentSelectionIssue,
    EquipmentSelectionIssueCode,
    can_place_decoration_in_equipment_slot,
    validate_build,
    validate_decoration_placements,
    validate_equipment_selection,
)
from mhwilds_skill_sim.validation.build import aggregate_valid_build_skill_levels


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
    part: EquipmentPart,
    *,
    equipment_id: str | None = None,
    skills: tuple[SkillContribution, ...] = (),
    slots: tuple[DecorationSlot, ...] = (),
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id or f"equipment:{part.value}",
        part=part,
        skills=skills,
        slots=slots,
        series_skill_id=series_skill_id,
        group_skill_id=group_skill_id,
    )


def complete_equipment(
    *,
    weapon_skills: tuple[SkillContribution, ...] = (),
    head_skills: tuple[SkillContribution, ...] = (),
    chest_skills: tuple[SkillContribution, ...] = (),
    arms_skills: tuple[SkillContribution, ...] = (),
    waist_skills: tuple[SkillContribution, ...] = (),
    legs_skills: tuple[SkillContribution, ...] = (),
    charm_skills: tuple[SkillContribution, ...] = (),
    weapon_slots: tuple[DecorationSlot, ...] = (),
    series_parts: tuple[EquipmentPart, ...] = (),
    group_parts: tuple[EquipmentPart, ...] = (),
    series_skill_id: str = "skill:series-bonus",
    group_skill_id: str = "skill:group-bonus",
) -> tuple[EquipmentDefinition, ...]:
    skills_by_part = {
        EquipmentPart.WEAPON: weapon_skills,
        EquipmentPart.HEAD: head_skills,
        EquipmentPart.CHEST: chest_skills,
        EquipmentPart.ARMS: arms_skills,
        EquipmentPart.WAIST: waist_skills,
        EquipmentPart.LEGS: legs_skills,
        EquipmentPart.CHARM: charm_skills,
    }
    return tuple(
        equipment_definition(
            part,
            skills=skills_by_part[part],
            slots=weapon_slots if part is EquipmentPart.WEAPON else (),
            series_skill_id=series_skill_id if part in series_parts else None,
            group_skill_id=group_skill_id if part in group_parts else None,
        )
        for part in REQUIRED_PARTS
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


def decoration_definition(
    decoration_id: str = "decoration:weapon-1",
    *,
    required_slot: DecorationSlot | None = None,
    skills: tuple[SkillContribution, ...] | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=required_slot or weapon_slot(1),
        skills=skills or (skill("skill:decoration-default", 1),),
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


def aggregate(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    decorations: tuple[DecorationDefinition, ...] = (),
    placements: tuple[DecorationPlacement, ...] = (),
    skill_definitions: tuple[SkillDefinition, ...] = (),
) -> dict[str, int]:
    return aggregate_valid_build_skill_levels(
        equipment=equipment if equipment is not None else complete_equipment(),
        decorations=decorations,
        placements=placements,
        skill_definitions=skill_definitions,
    )


def test_aggregates_equipment_skills_when_placements_are_empty() -> None:
    assert aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
            head_skills=(skill("skill:critical-eye", 2),),
        ),
    ) == {
        "skill:attack-boost": 1,
        "skill:critical-eye": 2,
    }


def test_aggregates_equipment_and_decoration_skills() -> None:
    assert aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
            weapon_slots=(weapon_slot(1),),
        ),
        decorations=(
            decoration_definition(
                skills=(skill("skill:critical-eye", 2),),
            ),
        ),
        placements=(placement(),),
    ) == {
        "skill:attack-boost": 1,
        "skill:critical-eye": 2,
    }


def test_sums_same_skill_id_from_equipment_and_decoration() -> None:
    assert aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 2),),
            weapon_slots=(weapon_slot(1),),
        ),
        decorations=(
            decoration_definition(
                skills=(skill("skill:attack-boost", 1),),
            ),
        ),
        placements=(placement(),),
    ) == {"skill:attack-boost": 3}


def test_sums_same_skill_id_from_multiple_equipment() -> None:
    assert aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
            head_skills=(skill("skill:attack-boost", 2),),
            chest_skills=(skill("skill:attack-boost", 3),),
        ),
    ) == {"skill:attack-boost": 6}


def test_sums_same_skill_id_from_multiple_decorations() -> None:
    assert aggregate(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1), weapon_slot(1))),
        decorations=(
            decoration_definition(
                "decoration:attack-a",
                skills=(skill("skill:attack-boost", 1),),
            ),
            decoration_definition(
                "decoration:attack-b",
                skills=(skill("skill:attack-boost", 2),),
            ),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:attack-a"),
            placement("equipment:weapon", 1, "decoration:attack-b"),
        ),
    ) == {"skill:attack-boost": 3}


def test_repeated_same_decoration_id_counts_each_placement() -> None:
    assert aggregate(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1), weapon_slot(1))),
        decorations=(
            decoration_definition(
                "decoration:attack",
                skills=(skill("skill:attack-boost", 2),),
            ),
        ),
        placements=(
            placement("equipment:weapon", 0, "decoration:attack"),
            placement("equipment:weapon", 1, "decoration:attack"),
        ),
    ) == {"skill:attack-boost": 4}


def test_ignores_equipment_without_skills() -> None:
    assert aggregate(
        equipment=complete_equipment(
            weapon_skills=(),
            head_skills=(skill("skill:critical-eye", 1),),
        ),
    ) == {"skill:critical-eye": 1}


def test_returns_empty_dict_when_no_equipment_or_decoration_skills() -> None:
    assert aggregate(equipment=complete_equipment(), placements=()) == {}


def test_preserves_skill_order_from_multi_skill_decoration() -> None:
    result = aggregate(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(
            decoration_definition(
                skills=(
                    skill("skill:critical-eye", 1),
                    skill("skill:weakness-exploit", 1),
                ),
            ),
        ),
        placements=(placement(),),
    )

    assert list(result) == ["skill:critical-eye", "skill:weakness-exploit"]


def test_result_key_order_is_equipment_first_then_decoration_first_seen_order() -> None:
    result = aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
            head_skills=(skill("skill:critical-eye", 1),),
            weapon_slots=(weapon_slot(1),),
        ),
        decorations=(
            decoration_definition(
                skills=(
                    skill("skill:weakness-exploit", 1),
                    skill("skill:attack-boost", 1),
                ),
            ),
        ),
        placements=(placement(),),
    )

    assert list(result) == [
        "skill:attack-boost",
        "skill:critical-eye",
        "skill:weakness-exploit",
    ]
    assert result == {
        "skill:attack-boost": 2,
        "skill:critical-eye": 1,
        "skill:weakness-exploit": 1,
    }


def test_aggregates_fixed_equipment_skills_plus_activated_series_skill() -> None:
    result = aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
            series_parts=(EquipmentPart.HEAD, EquipmentPart.CHEST),
        ),
        skill_definitions=(series_skill_definition(),),
    )

    assert result == {
        "skill:attack-boost": 1,
        "skill:series-bonus": 1,
    }


def test_aggregates_fixed_equipment_skills_plus_activated_group_skill() -> None:
    result = aggregate(
        equipment=complete_equipment(
            head_skills=(skill("skill:critical-eye", 1),),
            group_parts=(
                EquipmentPart.HEAD,
                EquipmentPart.CHEST,
                EquipmentPart.ARMS,
            ),
        ),
        skill_definitions=(group_skill_definition(),),
    )

    assert result == {
        "skill:critical-eye": 1,
        "skill:group-bonus": 1,
    }


def test_aggregates_simultaneous_series_and_group_activation() -> None:
    shared_parts = (
        EquipmentPart.HEAD,
        EquipmentPart.CHEST,
        EquipmentPart.ARMS,
    )

    assert aggregate(
        equipment=complete_equipment(
            series_parts=shared_parts,
            group_parts=shared_parts,
        ),
        skill_definitions=(series_skill_definition(), group_skill_definition()),
    ) == {
        "skill:series-bonus": 1,
        "skill:group-bonus": 1,
    }


def test_below_threshold_memberships_contribute_nothing() -> None:
    assert (
        aggregate(
            equipment=complete_equipment(series_parts=(EquipmentPart.HEAD,)),
            skill_definitions=(series_skill_definition(),),
        )
        == {}
    )


def test_only_highest_activated_bonus_rank_is_aggregated() -> None:
    assert aggregate(
        equipment=complete_equipment(
            series_parts=(
                EquipmentPart.HEAD,
                EquipmentPart.CHEST,
                EquipmentPart.ARMS,
                EquipmentPart.WAIST,
                EquipmentPart.LEGS,
            ),
        ),
        skill_definitions=(series_skill_definition(),),
    ) == {"skill:series-bonus": 2}


def test_skill_order_is_fixed_equipment_then_bonus_then_decoration() -> None:
    result = aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:fixed", 1),),
            weapon_slots=(weapon_slot(1),),
            series_parts=(EquipmentPart.HEAD, EquipmentPart.CHEST),
            group_parts=(
                EquipmentPart.HEAD,
                EquipmentPart.CHEST,
                EquipmentPart.ARMS,
            ),
        ),
        decorations=(decoration_definition(skills=(skill("skill:decoration", 1),)),),
        placements=(placement(),),
        skill_definitions=(group_skill_definition(), series_skill_definition()),
    )

    assert list(result) == [
        "skill:fixed",
        "skill:group-bonus",
        "skill:series-bonus",
        "skill:decoration",
    ]


def test_bonus_aggregation_returns_independent_dicts() -> None:
    equipment = complete_equipment(
        series_parts=(EquipmentPart.HEAD, EquipmentPart.CHEST),
    )
    skill_definitions = (series_skill_definition(),)

    first = aggregate(equipment=equipment, skill_definitions=skill_definitions)
    second = aggregate(equipment=equipment, skill_definitions=skill_definitions)

    assert first == second
    assert first is not second
    first["skill:series-bonus"] = 999
    assert second == {"skill:series-bonus": 1}


def test_default_skill_definitions_preserve_legacy_aggregation() -> None:
    signature = inspect.signature(aggregate_valid_build_skill_levels)

    assert signature.parameters["skill_definitions"].default == ()
    assert aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
        ),
    ) == {"skill:attack-boost": 1}


@pytest.mark.parametrize(
    ("field_name", "membership_id"),
    [
        ("series_skill_id", "skill:missing-series"),
        ("group_skill_id", "skill:missing-group"),
    ],
)
def test_unresolved_membership_errors_propagate(
    field_name: str,
    membership_id: str,
) -> None:
    membership_parts = (EquipmentPart.HEAD,)
    kwargs = {
        "series_parts": membership_parts if field_name == "series_skill_id" else (),
        "group_parts": membership_parts if field_name == "group_skill_id" else (),
        "series_skill_id": membership_id,
        "group_skill_id": membership_id,
    }

    with pytest.raises(ValueError) as exc_info:
        aggregate(equipment=complete_equipment(**kwargs))  # type: ignore[arg-type]

    assert "equipment" in str(exc_info.value)
    assert field_name in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "wrong_definition"),
    [
        (
            "series_skill_id",
            SkillDefinition(
                "skill:wrong",
                SkillKind.ARMOR,
                (SkillRankDefinition(1, None),),
            ),
        ),
        (
            "group_skill_id",
            series_skill_definition("skill:wrong", (1,)),
        ),
    ],
)
def test_wrong_kind_membership_errors_propagate(
    field_name: str,
    wrong_definition: SkillDefinition,
) -> None:
    membership_parts = (EquipmentPart.HEAD,)
    kwargs = {
        "series_parts": membership_parts if field_name == "series_skill_id" else (),
        "group_parts": membership_parts if field_name == "group_skill_id" else (),
        "series_skill_id": wrong_definition.skill_id,
        "group_skill_id": wrong_definition.skill_id,
    }

    with pytest.raises(ValueError) as exc_info:
        aggregate(
            equipment=complete_equipment(**kwargs),  # type: ignore[arg-type]
            skill_definitions=(wrong_definition,),
        )

    assert field_name in str(exc_info.value)


def test_invalid_build_fails_before_bonus_membership_resolution() -> None:
    incomplete_equipment = (
        equipment_definition(
            EquipmentPart.HEAD,
            series_skill_id="skill:missing-series",
        ),
    )

    with pytest.raises(ValueError, match="build"):
        aggregate_valid_build_skill_levels(
            equipment=incomplete_equipment,
            decorations=(),
            placements=(),
        )


def test_returns_new_dict_each_call() -> None:
    first = aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
        ),
    )
    second = aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
        ),
    )

    assert first == second
    assert first is not second


def test_mutating_result_does_not_affect_next_call() -> None:
    result = aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
        ),
    )
    result["skill:attack-boost"] = 999

    assert aggregate(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
        ),
    ) == {"skill:attack-boost": 1}


def test_aggregate_valid_build_skill_levels_requires_keyword_arguments() -> None:
    with pytest.raises(TypeError):
        aggregate_valid_build_skill_levels(complete_equipment(), (), ())  # type: ignore[misc]


def test_validation_package_exports_aggregate_valid_build_skill_levels() -> None:
    from mhwilds_skill_sim.validation import (
        aggregate_valid_build_skill_levels as exported_aggregate,
    )

    assert exported_aggregate is aggregate_valid_build_skill_levels


def test_validation_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.validation import (
        BuildValidationResult as ExportedBuildValidationResult,
        DecorationPlacement as ExportedDecorationPlacement,
        DecorationPlacementIssue as ExportedDecorationPlacementIssue,
        DecorationPlacementIssueCode as ExportedDecorationPlacementIssueCode,
        EquipmentSelectionIssue as ExportedEquipmentSelectionIssue,
        EquipmentSelectionIssueCode as ExportedEquipmentSelectionIssueCode,
        can_place_decoration_in_equipment_slot as exported_slot_validator,
        validate_build as exported_validate_build,
        validate_decoration_placements as exported_placement_validator,
        validate_equipment_selection as exported_equipment_validator,
    )

    assert ExportedBuildValidationResult is BuildValidationResult
    assert ExportedDecorationPlacement is DecorationPlacement
    assert ExportedDecorationPlacementIssue is DecorationPlacementIssue
    assert ExportedDecorationPlacementIssueCode is DecorationPlacementIssueCode
    assert ExportedEquipmentSelectionIssue is EquipmentSelectionIssue
    assert ExportedEquipmentSelectionIssueCode is EquipmentSelectionIssueCode
    assert exported_slot_validator is can_place_decoration_in_equipment_slot
    assert exported_validate_build is validate_build
    assert exported_placement_validator is validate_decoration_placements
    assert exported_equipment_validator is validate_equipment_selection


def test_rejects_build_with_equipment_selection_issues() -> None:
    with pytest.raises(ValueError, match="build"):
        aggregate(equipment=())


@pytest.mark.parametrize(
    "placements",
    [
        (placement("equipment:unknown", 0, "decoration:weapon-1"),),
        (placement("equipment:weapon", 0, "decoration:unknown"),),
        (placement("equipment:weapon", 1, "decoration:weapon-1"),),
    ],
)
def test_rejects_build_with_basic_decoration_placement_issues(
    placements: tuple[DecorationPlacement, ...],
) -> None:
    with pytest.raises(ValueError, match="build"):
        aggregate(
            equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
            decorations=(decoration_definition(),),
            placements=placements,
        )


def test_rejects_build_with_duplicate_slot_issue() -> None:
    with pytest.raises(ValueError, match="build"):
        aggregate(
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


def test_rejects_build_with_incompatible_slot_issue() -> None:
    with pytest.raises(ValueError, match="build"):
        aggregate(
            equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
            decorations=(
                decoration_definition(
                    required_slot=armor_slot(1),
                    skills=(skill("skill:attack-boost", 1),),
                ),
            ),
            placements=(placement(),),
        )


def test_propagates_equipment_tuple_errors() -> None:
    with pytest.raises(TypeError, match="equipment"):
        aggregate_valid_build_skill_levels(
            equipment=[],  # type: ignore[arg-type]
            decorations=(),
            placements=(),
        )


def test_propagates_decoration_tuple_errors() -> None:
    with pytest.raises(TypeError, match="decorations"):
        aggregate_valid_build_skill_levels(
            equipment=complete_equipment(),
            decorations=[],  # type: ignore[arg-type]
            placements=(),
        )


def test_propagates_placement_tuple_errors() -> None:
    with pytest.raises(TypeError, match="placements"):
        aggregate_valid_build_skill_levels(
            equipment=complete_equipment(),
            decorations=(),
            placements=[],  # type: ignore[arg-type]
        )


def test_propagates_equipment_element_errors() -> None:
    with pytest.raises(TypeError, match="equipment"):
        aggregate_valid_build_skill_levels(
            equipment=("equipment:weapon",),  # type: ignore[arg-type]
            decorations=(),
            placements=(),
        )


def test_propagates_decoration_element_errors() -> None:
    with pytest.raises(TypeError, match="decorations"):
        aggregate_valid_build_skill_levels(
            equipment=complete_equipment(),
            decorations=("decoration:weapon-1",),  # type: ignore[arg-type]
            placements=(),
        )


def test_propagates_placement_element_errors() -> None:
    with pytest.raises(TypeError, match="placements"):
        aggregate_valid_build_skill_levels(
            equipment=complete_equipment(),
            decorations=(),
            placements=("placement",),  # type: ignore[arg-type]
        )


def test_propagates_duplicate_equipment_id_errors() -> None:
    equipment = (
        equipment_definition(
            EquipmentPart.WEAPON,
            equipment_id="equipment:duplicate",
        ),
        equipment_definition(
            EquipmentPart.HEAD,
            equipment_id="equipment:duplicate",
        ),
        *(equipment_definition(part) for part in REQUIRED_PARTS[2:]),
    )

    with pytest.raises(ValueError, match="equipment"):
        aggregate_valid_build_skill_levels(
            equipment=equipment,
            decorations=(),
            placements=(),
        )


def test_propagates_duplicate_decoration_id_errors() -> None:
    with pytest.raises(ValueError, match="decorations"):
        aggregate_valid_build_skill_levels(
            equipment=complete_equipment(),
            decorations=(
                decoration_definition("decoration:duplicate"),
                decoration_definition("decoration:duplicate"),
            ),
            placements=(),
        )
