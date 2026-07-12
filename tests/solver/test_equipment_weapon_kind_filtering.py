from __future__ import annotations

import inspect
from collections.abc import Iterator

import pytest

import mhwilds_skill_sim.solver as solver
from mhwilds_skill_sim.domain.equipment import (
    EquipmentDefinition,
    EquipmentPart,
    WeaponKind,
)
from mhwilds_skill_sim.solver.equipment_filtering import (
    filter_equipment_candidates_by_weapon_kind,
)


def equipment_definition(
    equipment_id: str,
    *,
    part: EquipmentPart = EquipmentPart.WEAPON,
    weapon_kind: WeaponKind | None = None,
    display_name: str | None = None,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=(),
        slots=(),
        display_name=display_name,
        weapon_kind=weapon_kind,
    )


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment_definition(
        "equipment:weapon:great-sword",
        weapon_kind=WeaponKind.GREAT_SWORD,
    )


class EquipmentTuple(tuple):
    pass


def filter_equipment(
    *,
    equipment: tuple[EquipmentDefinition, ...],
    weapon_kind: WeaponKind | None,
) -> tuple[EquipmentDefinition, ...]:
    return filter_equipment_candidates_by_weapon_kind(
        equipment=equipment,
        weapon_kind=weapon_kind,
    )


def test_empty_input_returns_exact_empty_tuple() -> None:
    result = filter_equipment(equipment=(), weapon_kind=WeaponKind.GREAT_SWORD)

    assert type(result) is tuple
    assert result == ()


def test_none_weapon_kind_retains_every_item() -> None:
    great_sword = equipment_definition(
        "equipment:weapon:great-sword",
        weapon_kind=WeaponKind.GREAT_SWORD,
    )
    head = equipment_definition("equipment:head", part=EquipmentPart.HEAD)
    legacy_weapon = equipment_definition("equipment:weapon:legacy")
    equipment = (great_sword, head, legacy_weapon)

    result = filter_equipment(equipment=equipment, weapon_kind=None)

    assert result == equipment
    assert result is not equipment
    assert all(actual is expected for actual, expected in zip(result, equipment))


def test_selected_kind_retains_matching_weapons_and_all_non_weapons() -> None:
    great_sword = equipment_definition(
        "equipment:weapon:great-sword",
        weapon_kind=WeaponKind.GREAT_SWORD,
    )
    head = equipment_definition("equipment:head", part=EquipmentPart.HEAD)
    bow = equipment_definition(
        "equipment:weapon:bow",
        weapon_kind=WeaponKind.BOW,
    )
    charm = equipment_definition("equipment:charm", part=EquipmentPart.CHARM)

    assert filter_equipment(
        equipment=(great_sword, head, bow, charm),
        weapon_kind=WeaponKind.GREAT_SWORD,
    ) == (great_sword, head, charm)


def test_selected_kind_excludes_legacy_weapon_without_weapon_kind() -> None:
    legacy_weapon = equipment_definition(
        "equipment:weapon:great-sword-looking-id",
        display_name="Great Sword Looking Name",
    )
    head = equipment_definition("equipment:head", part=EquipmentPart.HEAD)

    assert filter_equipment(
        equipment=(legacy_weapon, head),
        weapon_kind=WeaponKind.GREAT_SWORD,
    ) == (head,)


@pytest.mark.parametrize("weapon_kind", tuple(WeaponKind))
def test_every_weapon_kind_selects_only_its_matching_weapon(
    weapon_kind: WeaponKind,
) -> None:
    other_kind = (
        WeaponKind.BOW if weapon_kind is not WeaponKind.BOW else WeaponKind.GREAT_SWORD
    )
    matching_weapon = equipment_definition(
        f"equipment:weapon:{weapon_kind.value}",
        weapon_kind=weapon_kind,
    )
    other_weapon = equipment_definition(
        f"equipment:weapon:{other_kind.value}",
        weapon_kind=other_kind,
    )
    armor = equipment_definition("equipment:head", part=EquipmentPart.HEAD)

    assert filter_equipment(
        equipment=(matching_weapon, other_weapon, armor),
        weapon_kind=weapon_kind,
    ) == (matching_weapon, armor)


def test_result_preserves_retained_input_order() -> None:
    head = equipment_definition("equipment:head", part=EquipmentPart.HEAD)
    bow = equipment_definition(
        "equipment:weapon:bow",
        weapon_kind=WeaponKind.BOW,
    )
    chest = equipment_definition("equipment:chest", part=EquipmentPart.CHEST)
    great_sword = equipment_definition(
        "equipment:weapon:great-sword",
        weapon_kind=WeaponKind.GREAT_SWORD,
    )
    arms = equipment_definition("equipment:arms", part=EquipmentPart.ARMS)

    assert filter_equipment(
        equipment=(head, bow, chest, great_sword, arms),
        weapon_kind=WeaponKind.BOW,
    ) == (head, bow, chest, arms)


def test_no_matching_weapon_leaves_only_non_weapon_candidates() -> None:
    bow = equipment_definition(
        "equipment:weapon:bow",
        weapon_kind=WeaponKind.BOW,
    )
    head = equipment_definition("equipment:head", part=EquipmentPart.HEAD)
    charm = equipment_definition("equipment:charm", part=EquipmentPart.CHARM)

    assert filter_equipment(
        equipment=(bow, head, charm),
        weapon_kind=WeaponKind.HAMMER,
    ) == (head, charm)


@pytest.mark.parametrize(
    "equipment",
    [
        [],
        set(),
        equipment_generator(),
        None,
    ],
)
def test_rejects_every_non_tuple_equipment_iterable(equipment: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        filter_equipment_candidates_by_weapon_kind(
            equipment=equipment,  # type: ignore[arg-type]
            weapon_kind=None,
        )


def test_rejects_tuple_subclass() -> None:
    equipment = EquipmentTuple(
        (
            equipment_definition(
                "equipment:weapon:great-sword",
                weapon_kind=WeaponKind.GREAT_SWORD,
            ),
        )
    )

    with pytest.raises(TypeError, match="equipment"):
        filter_equipment_candidates_by_weapon_kind(
            equipment=equipment,
            weapon_kind=None,
        )


@pytest.mark.parametrize("invalid_item", ["equipment:weapon", None, object()])
def test_rejects_invalid_equipment_elements(invalid_item: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        filter_equipment_candidates_by_weapon_kind(
            equipment=(invalid_item,),  # type: ignore[arg-type]
            weapon_kind=None,
        )


def test_duplicate_equipment_ids_are_rejected_before_filtering() -> None:
    first = equipment_definition(
        "equipment:weapon:duplicate",
        weapon_kind=WeaponKind.BOW,
    )
    second = equipment_definition(
        "equipment:weapon:duplicate",
        weapon_kind=WeaponKind.LANCE,
    )

    with pytest.raises(ValueError, match="equipment"):
        filter_equipment(
            equipment=(first, second),
            weapon_kind=WeaponKind.GREAT_SWORD,
        )


@pytest.mark.parametrize("invalid_weapon_kind", ["great-sword", object()])
def test_rejects_raw_string_and_other_invalid_weapon_kinds(
    invalid_weapon_kind: object,
) -> None:
    with pytest.raises(TypeError, match="weapon_kind"):
        filter_equipment_candidates_by_weapon_kind(
            equipment=(),
            weapon_kind=invalid_weapon_kind,  # type: ignore[arg-type]
        )


def test_input_and_equipment_objects_are_not_modified() -> None:
    weapon = equipment_definition(
        "equipment:weapon:great-sword",
        weapon_kind=WeaponKind.GREAT_SWORD,
        display_name="Great Sword",
    )
    head = equipment_definition("equipment:head", part=EquipmentPart.HEAD)
    equipment = (weapon, head)
    original_equipment = equipment

    result = filter_equipment(
        equipment=equipment,
        weapon_kind=WeaponKind.GREAT_SWORD,
    )

    assert equipment == original_equipment
    assert result[0] is weapon
    assert result[1] is head
    assert weapon.weapon_kind is WeaponKind.GREAT_SWORD
    assert weapon.display_name == "Great Sword"


def test_each_call_returns_a_new_outer_tuple() -> None:
    weapon = equipment_definition(
        "equipment:weapon:great-sword",
        weapon_kind=WeaponKind.GREAT_SWORD,
    )
    equipment = (weapon,)

    first = filter_equipment(equipment=equipment, weapon_kind=None)
    second = filter_equipment(equipment=equipment, weapon_kind=None)

    assert first == second == equipment
    assert first is not equipment
    assert second is not equipment
    assert first is not second


def test_arguments_are_keyword_only() -> None:
    signature = inspect.signature(filter_equipment_candidates_by_weapon_kind)

    assert signature.parameters["equipment"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["weapon_kind"].kind is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError):
        filter_equipment_candidates_by_weapon_kind(  # type: ignore[misc]
            (),
            WeaponKind.GREAT_SWORD,
        )


def test_solver_package_exports_equipment_filter_in_required_order() -> None:
    from mhwilds_skill_sim.solver import (
        filter_equipment_candidates_by_weapon_kind as exported_filter,
    )

    assert exported_filter is filter_equipment_candidates_by_weapon_kind
    assert solver.__all__ == [
        "BuildCandidate",
        "BuildCandidateSearchResult",
        "SkillRequirement",
        "enumerate_build_candidates",
        "enumerate_decoration_placement_combinations",
        "enumerate_equipment_selections",
        "expand_equipment_bonus_skill_variants",
        "filter_equipment_candidates_by_weapon_kind",
        "filter_build_candidates_by_skill_requirements",
        "generate_appraisal_charm_equipment_candidates",
        "search_catalog_build_candidates_by_skill_requirements",
        "search_build_candidates_by_skill_requirements",
        "search_limited_catalog_build_candidates_by_skill_requirements",
        "skill_levels_satisfy_requirements",
    ]


def test_existing_solver_exports_remain_available() -> None:
    existing_export_names = (
        "BuildCandidate",
        "BuildCandidateSearchResult",
        "SkillRequirement",
        "enumerate_build_candidates",
        "enumerate_decoration_placement_combinations",
        "enumerate_equipment_selections",
        "expand_equipment_bonus_skill_variants",
        "filter_build_candidates_by_skill_requirements",
        "generate_appraisal_charm_equipment_candidates",
        "search_catalog_build_candidates_by_skill_requirements",
        "search_build_candidates_by_skill_requirements",
        "search_limited_catalog_build_candidates_by_skill_requirements",
        "skill_levels_satisfy_requirements",
    )

    assert all(hasattr(solver, name) for name in existing_export_names)
