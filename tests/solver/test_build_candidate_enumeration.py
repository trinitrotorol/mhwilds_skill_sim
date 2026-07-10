from __future__ import annotations

import inspect
from collections.abc import Iterator
from dataclasses import FrozenInstanceError

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
from mhwilds_skill_sim.solver import (
    SkillRequirement,
    enumerate_decoration_placement_combinations,
    enumerate_equipment_selections,
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.solver.build import (
    BuildCandidate,
    enumerate_build_candidates,
)
from mhwilds_skill_sim.validation.placement import DecorationPlacement


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
    equipment_id: str | None = None,
    *,
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
    weapon_id: str = "equipment:weapon",
    head_id: str = "equipment:head",
    charm_id: str = "equipment:charm",
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
    return (
        equipment_definition(
            EquipmentPart.WEAPON,
            weapon_id,
            skills=weapon_skills,
            slots=weapon_slots,
            series_skill_id=(
                series_skill_id if EquipmentPart.WEAPON in series_parts else None
            ),
            group_skill_id=(
                group_skill_id if EquipmentPart.WEAPON in group_parts else None
            ),
        ),
        equipment_definition(
            EquipmentPart.HEAD,
            head_id,
            skills=head_skills,
            series_skill_id=(
                series_skill_id if EquipmentPart.HEAD in series_parts else None
            ),
            group_skill_id=(
                group_skill_id if EquipmentPart.HEAD in group_parts else None
            ),
        ),
        equipment_definition(
            EquipmentPart.CHEST,
            "equipment:chest",
            skills=chest_skills,
            series_skill_id=(
                series_skill_id if EquipmentPart.CHEST in series_parts else None
            ),
            group_skill_id=(
                group_skill_id if EquipmentPart.CHEST in group_parts else None
            ),
        ),
        equipment_definition(
            EquipmentPart.ARMS,
            "equipment:arms",
            skills=arms_skills,
            series_skill_id=(
                series_skill_id if EquipmentPart.ARMS in series_parts else None
            ),
            group_skill_id=(
                group_skill_id if EquipmentPart.ARMS in group_parts else None
            ),
        ),
        equipment_definition(
            EquipmentPart.WAIST,
            "equipment:waist",
            skills=waist_skills,
            series_skill_id=(
                series_skill_id if EquipmentPart.WAIST in series_parts else None
            ),
            group_skill_id=(
                group_skill_id if EquipmentPart.WAIST in group_parts else None
            ),
        ),
        equipment_definition(
            EquipmentPart.LEGS,
            "equipment:legs",
            skills=legs_skills,
            series_skill_id=(
                series_skill_id if EquipmentPart.LEGS in series_parts else None
            ),
            group_skill_id=(
                group_skill_id if EquipmentPart.LEGS in group_parts else None
            ),
        ),
        equipment_definition(
            EquipmentPart.CHARM,
            charm_id,
            skills=charm_skills,
            series_skill_id=(
                series_skill_id if EquipmentPart.CHARM in series_parts else None
            ),
            group_skill_id=(
                group_skill_id if EquipmentPart.CHARM in group_parts else None
            ),
        ),
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


def two_head_equipment(
    *,
    weapon_slots: tuple[DecorationSlot, ...] = (),
) -> tuple[EquipmentDefinition, ...]:
    return (
        equipment_definition(
            EquipmentPart.WEAPON,
            "equipment:weapon",
            slots=weapon_slots,
        ),
        equipment_definition(EquipmentPart.HEAD, "equipment:head-a"),
        equipment_definition(EquipmentPart.HEAD, "equipment:head-b"),
        *(
            equipment_definition(part, f"equipment:{part.value}")
            for part in REQUIRED_PARTS
            if part not in {EquipmentPart.WEAPON, EquipmentPart.HEAD}
        ),
    )


def two_head_two_charm_equipment() -> tuple[EquipmentDefinition, ...]:
    return (
        equipment_definition(EquipmentPart.WEAPON, "equipment:weapon"),
        equipment_definition(EquipmentPart.HEAD, "equipment:head-a"),
        equipment_definition(EquipmentPart.HEAD, "equipment:head-b"),
        equipment_definition(EquipmentPart.CHARM, "equipment:charm-a"),
        equipment_definition(EquipmentPart.CHARM, "equipment:charm-b"),
        *(
            equipment_definition(part, f"equipment:{part.value}")
            for part in REQUIRED_PARTS
            if part
            not in {EquipmentPart.WEAPON, EquipmentPart.HEAD, EquipmentPart.CHARM}
        ),
    )


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


def candidate(
    *,
    equipment: tuple[EquipmentDefinition, ...] | None = None,
    placements: tuple[DecorationPlacement, ...] = (),
    skill_levels: tuple[tuple[str, int], ...] = (("skill:attack-boost", 1),),
) -> BuildCandidate:
    return BuildCandidate(
        equipment=equipment
        if equipment is not None
        else (equipment_definition(EquipmentPart.WEAPON),),
        placements=placements,
        skill_levels=skill_levels,
    )


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition(EquipmentPart.WEAPON)


def placement_generator() -> Iterator[DecorationPlacement]:
    yield placement()


def skill_levels_generator() -> Iterator[tuple[str, int]]:
    yield ("skill:attack-boost", 1)


def decorations_generator() -> Iterator[DecorationDefinition]:
    yield decoration_definition()


def skill_definitions_generator() -> Iterator[SkillDefinition]:
    yield series_skill_definition()


class EquipmentTuple(tuple):
    pass


class PlacementTuple(tuple):
    pass


class SkillLevelsTuple(tuple):
    pass


class SkillLevelEntryTuple(tuple):
    pass


class DecorationTuple(tuple):
    pass


class SkillDefinitionTuple(tuple):
    pass


def equipment_ids(
    candidates: tuple[BuildCandidate, ...],
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(definition.equipment_id for definition in build.equipment)
        for build in candidates
    )


def test_build_candidate_keeps_valid_values() -> None:
    equipment = complete_equipment()
    placements = (placement(),)
    skill_levels = (("skill:attack-boost", 1),)

    build = BuildCandidate(
        equipment=equipment,
        placements=placements,
        skill_levels=skill_levels,
    )

    assert build.equipment == equipment
    assert build.placements == placements
    assert build.skill_levels == skill_levels


def test_build_candidate_value_semantics_and_hashing() -> None:
    assert candidate() == candidate()
    assert candidate() != candidate(skill_levels=(("skill:critical-eye", 1),))
    assert {candidate(), candidate()} == {candidate()}


def test_build_candidate_is_frozen() -> None:
    build = candidate()

    with pytest.raises(FrozenInstanceError):
        build.skill_levels = ()  # type: ignore[misc]


def test_solver_package_exports_build_candidate() -> None:
    from mhwilds_skill_sim.solver import BuildCandidate as ExportedBuildCandidate

    assert ExportedBuildCandidate is BuildCandidate


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_definition(EquipmentPart.WEAPON)],
        {equipment_definition(EquipmentPart.WEAPON)},
        equipment_generator(),
        None,
    ],
)
def test_build_candidate_rejects_non_tuple_equipment(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        BuildCandidate(
            equipment=equipment,  # type: ignore[arg-type]
            placements=(),
            skill_levels=(),
        )


def test_build_candidate_rejects_equipment_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="equipment"):
        candidate(
            equipment=EquipmentTuple((equipment_definition(EquipmentPart.WEAPON),))
        )


@pytest.mark.parametrize("invalid_equipment", ["equipment:weapon", None])
def test_build_candidate_rejects_invalid_equipment_elements(
    invalid_equipment: object,
) -> None:
    with pytest.raises(TypeError, match="equipment"):
        BuildCandidate(
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
            placements=(),
            skill_levels=(),
        )


@pytest.mark.parametrize(
    "placements",
    [[placement()], {placement()}, placement_generator(), None],
)
def test_build_candidate_rejects_non_tuple_placements(placements: object) -> None:
    with pytest.raises(TypeError, match="placements"):
        BuildCandidate(
            equipment=(),
            placements=placements,  # type: ignore[arg-type]
            skill_levels=(),
        )


def test_build_candidate_rejects_placements_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="placements"):
        BuildCandidate(
            equipment=(),
            placements=PlacementTuple((placement(),)),
            skill_levels=(),
        )


@pytest.mark.parametrize("invalid_placement", ["placement", None])
def test_build_candidate_rejects_invalid_placement_elements(
    invalid_placement: object,
) -> None:
    with pytest.raises(TypeError, match="placements"):
        BuildCandidate(
            equipment=(),
            placements=(invalid_placement,),  # type: ignore[arg-type]
            skill_levels=(),
        )


@pytest.mark.parametrize(
    "skill_levels",
    [
        [("skill:attack-boost", 1)],
        {("skill:attack-boost", 1)},
        skill_levels_generator(),
        None,
    ],
)
def test_build_candidate_rejects_non_tuple_skill_levels(
    skill_levels: object,
) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=skill_levels,  # type: ignore[arg-type]
        )


def test_build_candidate_rejects_skill_levels_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=SkillLevelsTuple((("skill:attack-boost", 1),)),
        )


@pytest.mark.parametrize("entry", [["skill:attack-boost", 1], "skill", None])
def test_build_candidate_rejects_non_tuple_skill_level_entries(entry: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=(entry,),  # type: ignore[arg-type]
        )


def test_build_candidate_rejects_skill_level_entry_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=(SkillLevelEntryTuple(("skill:attack-boost", 1)),),
        )


@pytest.mark.parametrize(
    "entry",
    [("skill:attack-boost",), ("skill:attack-boost", 1, 2)],
)
def test_build_candidate_rejects_wrong_length_skill_level_entries(
    entry: tuple[object, ...],
) -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        BuildCandidate(equipment=(), placements=(), skill_levels=(entry,))  # type: ignore[arg-type]


@pytest.mark.parametrize("skill_id", [1, None])
def test_build_candidate_rejects_non_string_skill_ids(skill_id: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=((skill_id, 1),),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "skill_id",
    ["", " ", "\t", " skill:attack-boost", "skill:attack-boost "],
)
def test_build_candidate_rejects_invalid_skill_id_text(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        BuildCandidate(equipment=(), placements=(), skill_levels=((skill_id, 1),))


@pytest.mark.parametrize("total_level", [True, 1.5, "1", None])
def test_build_candidate_rejects_non_int_total_levels(total_level: object) -> None:
    with pytest.raises(TypeError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=(("skill:attack-boost", total_level),),  # type: ignore[arg-type]
        )


def test_build_candidate_rejects_negative_total_level() -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=(("skill:attack-boost", -1),),
        )


def test_build_candidate_accepts_zero_total_level() -> None:
    assert candidate(skill_levels=(("skill:attack-boost", 0),)).skill_levels == (
        ("skill:attack-boost", 0),
    )


def test_build_candidate_rejects_duplicate_skill_ids() -> None:
    with pytest.raises(ValueError, match="skill_levels"):
        BuildCandidate(
            equipment=(),
            placements=(),
            skill_levels=(
                ("skill:attack-boost", 1),
                ("skill:attack-boost", 2),
            ),
        )


def test_empty_decorations_return_one_candidate_for_complete_equipment() -> None:
    equipment = complete_equipment(
        weapon_skills=(skill("skill:attack-boost", 1),),
        head_skills=(skill("skill:critical-eye", 2),),
    )

    candidates = enumerate_build_candidates(equipment=equipment, decorations=())

    assert len(candidates) == 1
    assert candidates[0].equipment == equipment
    assert (
        tuple(definition.part for definition in candidates[0].equipment)
        == REQUIRED_PARTS
    )
    assert candidates[0].placements == ()
    assert candidates[0].skill_levels == (
        ("skill:attack-boost", 1),
        ("skill:critical-eye", 2),
    )


def test_candidate_skill_levels_are_empty_when_no_skills_exist() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(), decorations=()
    )

    assert candidates[0].skill_levels == ()


def test_candidates_include_activated_series_and_group_skill_levels() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(
            series_parts=(
                EquipmentPart.HEAD,
                EquipmentPart.CHEST,
                EquipmentPart.ARMS,
                EquipmentPart.WAIST,
            ),
            group_parts=(
                EquipmentPart.HEAD,
                EquipmentPart.CHEST,
                EquipmentPart.ARMS,
            ),
        ),
        decorations=(),
        skill_definitions=(series_skill_definition(), group_skill_definition()),
    )

    assert candidates[0].skill_levels == (
        ("skill:series-bonus", 2),
        ("skill:group-bonus", 1),
    )


def test_candidates_omit_memberships_below_activation_threshold() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(series_parts=(EquipmentPart.HEAD,)),
        decorations=(),
        skill_definitions=(series_skill_definition(),),
    )

    assert candidates[0].skill_levels == ()


def test_skill_definitions_do_not_change_candidate_order() -> None:
    equipment = two_head_equipment(weapon_slots=(weapon_slot(1),))
    decorations = (decoration_definition(),)

    legacy = enumerate_build_candidates(
        equipment=equipment,
        decorations=decorations,
    )
    with_definitions = enumerate_build_candidates(
        equipment=equipment,
        decorations=decorations,
        skill_definitions=(series_skill_definition(), group_skill_definition()),
    )

    assert [(build.equipment, build.placements) for build in with_definitions] == [
        (build.equipment, build.placements) for build in legacy
    ]


def test_direct_enumeration_without_memberships_remains_backward_compatible() -> None:
    equipment = complete_equipment(
        weapon_skills=(skill("skill:attack-boost", 1),),
    )

    assert enumerate_build_candidates(
        equipment=equipment,
        decorations=(),
    ) == enumerate_build_candidates(
        equipment=equipment,
        decorations=(),
        skill_definitions=(),
    )


def test_two_head_candidates_return_two_build_candidates() -> None:
    candidates = enumerate_build_candidates(
        equipment=two_head_equipment(), decorations=()
    )

    assert len(candidates) == 2


def test_two_head_and_two_charm_candidates_return_four_build_candidates() -> None:
    candidates = enumerate_build_candidates(
        equipment=two_head_two_charm_equipment(),
        decorations=(),
    )

    assert len(candidates) == 4


def test_one_slot_with_one_decoration_returns_empty_and_filled_candidates() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(decoration_definition(),),
    )

    assert len(candidates) == 2
    assert candidates[0].placements == ()
    assert candidates[1].placements == (placement(),)


def test_two_slots_return_candidate_for_each_placement_combination() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1), armor_slot(1))),
        decorations=(
            decoration_definition("decoration:weapon", required_slot=weapon_slot(1)),
            decoration_definition("decoration:armor", required_slot=armor_slot(1)),
        ),
    )

    assert tuple(build.placements for build in candidates) == (
        (),
        (placement(decoration_id="decoration:armor", slot_index=1),),
        (placement(decoration_id="decoration:weapon", slot_index=0),),
        (
            placement(decoration_id="decoration:weapon", slot_index=0),
            placement(decoration_id="decoration:armor", slot_index=1),
        ),
    )


def test_candidate_order_uses_equipment_selection_order_then_placement_order() -> None:
    candidates = enumerate_build_candidates(
        equipment=two_head_equipment(weapon_slots=(weapon_slot(1),)),
        decorations=(decoration_definition(),),
    )

    assert [
        (build.equipment[1].equipment_id, build.placements) for build in candidates
    ] == [
        ("equipment:head-a", ()),
        ("equipment:head-a", (placement(),)),
        ("equipment:head-b", ()),
        ("equipment:head-b", (placement(),)),
    ]


def test_candidates_include_same_decoration_id_on_multiple_slots() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(weapon_slots=(weapon_slot(1), weapon_slot(1))),
        decorations=(decoration_definition("decoration:shared"),),
    )

    assert (
        placement(slot_index=0, decoration_id="decoration:shared"),
        placement(slot_index=1, decoration_id="decoration:shared"),
    ) in tuple(build.placements for build in candidates)


def test_skill_level_order_is_equipment_first_then_decoration_first_seen_order() -> (
    None
):
    candidates = enumerate_build_candidates(
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
    )

    assert candidates[1].skill_levels == (
        ("skill:attack-boost", 2),
        ("skill:critical-eye", 1),
        ("skill:weakness-exploit", 1),
    )


def test_return_value_and_candidates_are_tuples_and_build_candidates() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(), decorations=()
    )

    assert type(candidates) is tuple
    assert all(isinstance(build, BuildCandidate) for build in candidates)


def test_returns_new_tuple_each_call() -> None:
    first = enumerate_build_candidates(equipment=complete_equipment(), decorations=())
    second = enumerate_build_candidates(equipment=complete_equipment(), decorations=())

    assert first == second
    assert first is not second


def test_inputs_are_not_modified() -> None:
    equipment = complete_equipment(weapon_slots=(weapon_slot(1),))
    decorations = (decoration_definition(),)
    skill_definitions = (series_skill_definition(),)
    original_equipment = equipment
    original_decorations = decorations
    original_skill_definitions = skill_definitions

    enumerate_build_candidates(
        equipment=equipment,
        decorations=decorations,
        skill_definitions=skill_definitions,
    )

    assert equipment == original_equipment
    assert decorations == original_decorations
    assert skill_definitions == original_skill_definitions


def test_enumerate_build_candidates_requires_keyword_arguments() -> None:
    signature = inspect.signature(enumerate_build_candidates)

    assert signature.parameters["equipment"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["decorations"].kind is inspect.Parameter.KEYWORD_ONLY
    assert (
        signature.parameters["skill_definitions"].kind is inspect.Parameter.KEYWORD_ONLY
    )
    assert signature.parameters["skill_definitions"].default == ()

    with pytest.raises(TypeError):
        enumerate_build_candidates(complete_equipment(), ())  # type: ignore[call-arg]


def test_solver_package_exports_enumerate_build_candidates() -> None:
    from mhwilds_skill_sim.solver import (
        enumerate_build_candidates as exported_function,
    )

    assert exported_function is enumerate_build_candidates


def test_solver_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.solver import (
        enumerate_decoration_placement_combinations as exported_decorations,
    )
    from mhwilds_skill_sim.solver import (
        enumerate_equipment_selections as exported_equipment,
    )
    from mhwilds_skill_sim.solver import SkillRequirement as ExportedRequirement
    from mhwilds_skill_sim.solver import (
        skill_levels_satisfy_requirements as exported_requirements,
    )

    assert exported_decorations is enumerate_decoration_placement_combinations
    assert exported_equipment is enumerate_equipment_selections
    assert ExportedRequirement is SkillRequirement
    assert exported_requirements is skill_levels_satisfy_requirements


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
            if part is not EquipmentPart.CHARM
        ),
        (
            equipment_definition(EquipmentPart.WEAPON),
            equipment_definition(EquipmentPart.HEAD),
        ),
    ],
)
def test_missing_equipment_cases_return_empty_tuple(
    equipment: tuple[EquipmentDefinition, ...],
) -> None:
    assert enumerate_build_candidates(equipment=equipment, decorations=()) == ()


@pytest.mark.parametrize(
    "equipment",
    [
        [equipment_definition(EquipmentPart.WEAPON)],
        {equipment_definition(EquipmentPart.WEAPON)},
        equipment_generator(),
        None,
    ],
)
def test_rejects_non_tuple_equipment(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        enumerate_build_candidates(
            equipment=equipment,  # type: ignore[arg-type]
            decorations=(),
        )


def test_rejects_equipment_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="equipment"):
        enumerate_build_candidates(
            equipment=EquipmentTuple((equipment_definition(EquipmentPart.WEAPON),)),
            decorations=(),
        )


@pytest.mark.parametrize(
    "decorations",
    [
        [decoration_definition()],
        {decoration_definition()},
        decorations_generator(),
        None,
    ],
)
def test_rejects_non_tuple_decorations(decorations: object) -> None:
    with pytest.raises(TypeError, match="decorations"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=decorations,  # type: ignore[arg-type]
        )


def test_rejects_decorations_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="decorations"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=DecorationTuple((decoration_definition(),)),
        )


@pytest.mark.parametrize(
    "skill_definitions",
    [
        [series_skill_definition()],
        {series_skill_definition()},
        skill_definitions_generator(),
        None,
    ],
)
def test_rejects_non_tuple_skill_definitions(skill_definitions: object) -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=(),
            skill_definitions=skill_definitions,  # type: ignore[arg-type]
        )


def test_rejects_skill_definitions_tuple_subclass() -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=(),
            skill_definitions=SkillDefinitionTuple((series_skill_definition(),)),
        )


@pytest.mark.parametrize("invalid_definition", ["skill", None, 1])
def test_rejects_invalid_skill_definition_elements(
    invalid_definition: object,
) -> None:
    with pytest.raises(TypeError, match="skill_definitions"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=(),
            skill_definitions=(invalid_definition,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_skill_definition_ids() -> None:
    with pytest.raises(ValueError, match="skill_definitions"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=(),
            skill_definitions=(
                series_skill_definition("skill:duplicate", (1,)),
                group_skill_definition("skill:duplicate", (1,)),
            ),
        )


@pytest.mark.parametrize("invalid_equipment", ["equipment:weapon", None])
def test_rejects_invalid_equipment_elements(invalid_equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        enumerate_build_candidates(
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
            decorations=(),
        )


@pytest.mark.parametrize("invalid_decoration", ["decoration:weapon", None])
def test_rejects_invalid_decoration_elements(invalid_decoration: object) -> None:
    with pytest.raises(TypeError, match="decorations"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=(invalid_decoration,),  # type: ignore[arg-type]
        )


def test_rejects_duplicate_equipment_id() -> None:
    equipment = (
        equipment_definition(EquipmentPart.WEAPON, "equipment:duplicate"),
        equipment_definition(EquipmentPart.HEAD, "equipment:duplicate"),
        *(
            equipment_definition(part, f"equipment:{part.value}")
            for part in REQUIRED_PARTS
            if part not in {EquipmentPart.WEAPON, EquipmentPart.HEAD}
        ),
    )

    with pytest.raises(ValueError, match="equipment"):
        enumerate_build_candidates(equipment=equipment, decorations=())


def test_rejects_duplicate_decoration_id() -> None:
    with pytest.raises(ValueError, match="decorations"):
        enumerate_build_candidates(
            equipment=complete_equipment(),
            decorations=(
                decoration_definition("decoration:duplicate"),
                decoration_definition("decoration:duplicate"),
            ),
        )


def test_allows_same_text_in_equipment_id_and_decoration_id() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(
            weapon_id="shared:id",
            weapon_slots=(weapon_slot(1),),
        ),
        decorations=(decoration_definition("shared:id"),),
    )

    assert (placement("shared:id", 0, "shared:id"),) in tuple(
        build.placements for build in candidates
    )


def test_does_not_filter_candidates_by_skill_requirements() -> None:
    candidates = enumerate_build_candidates(
        equipment=complete_equipment(
            weapon_skills=(skill("skill:attack-boost", 1),),
        ),
        decorations=(),
    )

    assert len(candidates) == 1
    assert not skill_levels_satisfy_requirements(
        skill_levels=dict(candidates[0].skill_levels),
        requirements=(SkillRequirement("skill:attack-boost", 2),),
    )
