from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.catalog import Catalog
from mhwilds_skill_sim.domain.appraisal import (
    AppraisalCharmPatternDefinition,
    AppraisalCharmSkillGroupDefinition,
)
from mhwilds_skill_sim.domain.decoration import DecorationDefinition
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.domain.skill import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
)
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def equipment(
    equipment_id: str = "equipment:weapon:training-blade",
    skills: tuple[SkillContribution, ...] | None = None,
    slots: tuple[DecorationSlot, ...] | None = None,
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
    additional_series_skill_ids: tuple[str, ...] = (),
    additional_group_skill_ids: tuple[str, ...] = (),
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=EquipmentPart.WEAPON,
        skills=skills if skills is not None else (skill(),),
        slots=slots if slots is not None else (weapon_slot(1),),
        series_skill_id=series_skill_id,
        group_skill_id=group_skill_id,
        allows_series_skill_assignment=allows_series_skill_assignment,
        allows_group_skill_assignment=allows_group_skill_assignment,
        additional_series_skill_ids=additional_series_skill_ids,
        additional_group_skill_ids=additional_group_skill_ids,
    )


def decoration(
    decoration_id: str = "decoration:weapon-power-1",
    skills: tuple[SkillContribution, ...] | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=weapon_slot(1),
        skills=skills if skills is not None else (skill(),),
    )


def skill_definition(
    skill_id: str = "skill:attack-boost",
    kind: SkillKind = SkillKind.ARMOR,
    ranks: tuple[SkillRankDefinition, ...] = (SkillRankDefinition(1, None),),
) -> SkillDefinition:
    return SkillDefinition(skill_id=skill_id, kind=kind, ranks=ranks)


def series_skill_definition(
    skill_id: str = "skill:fixture-series-bonus",
) -> SkillDefinition:
    return skill_definition(
        skill_id,
        SkillKind.SERIES,
        (SkillRankDefinition(1, 2), SkillRankDefinition(2, 4)),
    )


def group_skill_definition(
    skill_id: str = "skill:fixture-group-bonus",
) -> SkillDefinition:
    return skill_definition(
        skill_id,
        SkillKind.GROUP,
        (SkillRankDefinition(1, 3),),
    )


def appraisal_skill_group(
    group_id: str = "appraisal-group:A",
    skills: tuple[SkillContribution, ...] | None = None,
) -> AppraisalCharmSkillGroupDefinition:
    return AppraisalCharmSkillGroupDefinition(
        group_id=group_id,
        skills=skills if skills is not None else (skill(),),
    )


def appraisal_pattern(
    pattern_id: str = "appraisal-pattern:r8-a",
    skill_group_ids: tuple[str, ...] = ("appraisal-group:A",),
    rarity: int = 8,
    slots: tuple[DecorationSlot, ...] = (),
) -> AppraisalCharmPatternDefinition:
    return AppraisalCharmPatternDefinition(
        pattern_id=pattern_id,
        rarity=rarity,
        skill_group_ids=skill_group_ids,
        slots=slots,
    )


def catalog(
    schema_version: int = 1,
    equipment_items: tuple[EquipmentDefinition, ...] | None = None,
    decoration_items: tuple[DecorationDefinition, ...] | None = None,
    skill_items: tuple[SkillDefinition, ...] | None = None,
    appraisal_group_items: tuple[AppraisalCharmSkillGroupDefinition, ...] | None = None,
    appraisal_pattern_items: tuple[AppraisalCharmPatternDefinition, ...] | None = None,
) -> Catalog:
    return Catalog(
        schema_version=schema_version,
        equipment=equipment_items if equipment_items is not None else (equipment(),),
        decorations=(
            decoration_items if decoration_items is not None else (decoration(),)
        ),
        skills=skill_items if skill_items is not None else (),
        appraisal_charm_skill_groups=(
            appraisal_group_items if appraisal_group_items is not None else ()
        ),
        appraisal_charm_patterns=(
            appraisal_pattern_items if appraisal_pattern_items is not None else ()
        ),
    )


def test_can_create_empty_catalog() -> None:
    created = Catalog(schema_version=1, equipment=(), decorations=())

    assert created.schema_version == 1
    assert created.equipment == ()
    assert created.decorations == ()
    assert created.skills == ()


def test_can_create_catalog_with_equipment_and_decorations() -> None:
    equipment_items = (equipment("equipment:weapon:training-blade"),)
    decoration_items = (decoration("decoration:weapon-power-1"),)

    created = Catalog(
        schema_version=1,
        equipment=equipment_items,
        decorations=decoration_items,
    )

    assert created.equipment == equipment_items
    assert created.decorations == decoration_items
    assert created.skills == ()


def test_legacy_catalog_without_memberships_or_skills_remains_valid() -> None:
    legacy_equipment = EquipmentDefinition(
        equipment_id="equipment:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(skill(),),
        slots=(weapon_slot(),),
    )

    created = Catalog(
        schema_version=1,
        equipment=(legacy_equipment,),
        decorations=(),
    )

    assert created.equipment == (legacy_equipment,)
    assert created.skills == ()


def test_catalog_accepts_valid_series_membership_reference() -> None:
    series_skill = series_skill_definition()
    equipment_item = equipment(series_skill_id=series_skill.skill_id)

    created = catalog(
        equipment_items=(equipment_item,),
        skill_items=(series_skill,),
    )

    assert created.equipment[0].series_skill_id == series_skill.skill_id


def test_catalog_accepts_valid_group_membership_reference() -> None:
    group_skill = group_skill_definition()
    equipment_item = equipment(group_skill_id=group_skill.skill_id)

    created = catalog(
        equipment_items=(equipment_item,),
        skill_items=(group_skill,),
    )

    assert created.equipment[0].group_skill_id == group_skill.skill_id


def test_catalog_accepts_simultaneous_membership_references() -> None:
    series_skill = series_skill_definition()
    group_skill = group_skill_definition()
    equipment_item = equipment(
        series_skill_id=series_skill.skill_id,
        group_skill_id=group_skill.skill_id,
    )

    created = catalog(
        equipment_items=(equipment_item,),
        skill_items=(series_skill, group_skill),
    )

    assert created.equipment == (equipment_item,)


def test_catalog_accepts_complete_series_and_group_membership_references() -> None:
    primary_series = series_skill_definition("skill:series-primary")
    extra_series = series_skill_definition("skill:series-extra")
    primary_group = group_skill_definition("skill:group-primary")
    extra_group = group_skill_definition("skill:group-extra")
    equipment_item = equipment(
        series_skill_id=primary_series.skill_id,
        group_skill_id=primary_group.skill_id,
        additional_series_skill_ids=(extra_series.skill_id,),
        additional_group_skill_ids=(extra_group.skill_id,),
    )

    created = catalog(
        equipment_items=(equipment_item,),
        skill_items=(primary_series, extra_series, primary_group, extra_group),
    )

    assert created.equipment[0].series_skill_ids == (
        primary_series.skill_id,
        extra_series.skill_id,
    )
    assert created.equipment[0].group_skill_ids == (
        primary_group.skill_id,
        extra_group.skill_id,
    )


@pytest.mark.parametrize(
    ("field_name", "missing_skill_id"),
    [
        ("additional_series_skill_ids", "skill:missing-series"),
        ("additional_group_skill_ids", "skill:missing-group"),
    ],
)
def test_catalog_rejects_missing_additional_membership_reference(
    field_name: str,
    missing_skill_id: str,
) -> None:
    memberships = {field_name: (missing_skill_id,)}
    equipment_item = EquipmentDefinition(
        equipment_id="equipment:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(),
        slots=(),
        **memberships,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError) as exc_info:
        catalog(equipment_items=(equipment_item,), skill_items=())

    assert "equipment" in str(exc_info.value)
    assert field_name.replace("additional_", "") in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "wrong_skill"),
    [
        (
            "additional_series_skill_ids",
            skill_definition("skill:wrong-series", SkillKind.ARMOR),
        ),
        (
            "additional_series_skill_ids",
            group_skill_definition("skill:wrong-series"),
        ),
        (
            "additional_group_skill_ids",
            skill_definition("skill:wrong-group", SkillKind.WEAPON),
        ),
        (
            "additional_group_skill_ids",
            series_skill_definition("skill:wrong-group"),
        ),
    ],
)
def test_catalog_rejects_additional_membership_reference_to_wrong_kind(
    field_name: str,
    wrong_skill: SkillDefinition,
) -> None:
    memberships = {field_name: (wrong_skill.skill_id,)}
    equipment_item = EquipmentDefinition(
        equipment_id="equipment:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(),
        slots=(),
        **memberships,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError) as exc_info:
        catalog(
            equipment_items=(equipment_item,),
            skill_items=(wrong_skill,),
        )

    assert "equipment" in str(exc_info.value)
    assert field_name.replace("additional_", "") in str(exc_info.value)


def test_catalog_allows_unused_series_and_group_skill_definitions() -> None:
    skill_items = (series_skill_definition(), group_skill_definition())

    created = catalog(skill_items=skill_items)

    assert created.skills == skill_items


def test_catalog_accepts_series_assignment_with_available_series_skill() -> None:
    series_skill = series_skill_definition()
    equipment_item = equipment(allows_series_skill_assignment=True)

    created = catalog(
        equipment_items=(equipment_item,),
        skill_items=(series_skill,),
    )

    assert created.equipment == (equipment_item,)


def test_catalog_accepts_group_assignment_with_available_group_skill() -> None:
    group_skill = group_skill_definition()
    equipment_item = equipment(allows_group_skill_assignment=True)

    created = catalog(
        equipment_items=(equipment_item,),
        skill_items=(group_skill,),
    )

    assert created.equipment == (equipment_item,)


def test_catalog_accepts_simultaneous_assignment_availability() -> None:
    equipment_item = equipment(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )

    created = catalog(
        equipment_items=(equipment_item,),
        skill_items=(series_skill_definition(), group_skill_definition()),
    )

    assert created.equipment == (equipment_item,)


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
def test_catalog_rejects_assignment_without_matching_skill_kind(
    field_name: str,
) -> None:
    assignments = {field_name: True}
    equipment_item = EquipmentDefinition(
        equipment_id="equipment:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(),
        slots=(),
        **assignments,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError) as exc_info:
        catalog(equipment_items=(equipment_item,), skill_items=())

    assert "equipment" in str(exc_info.value)
    assert field_name in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "unrelated_skill"),
    [
        (
            "allows_series_skill_assignment",
            skill_definition("skill:armor", SkillKind.ARMOR),
        ),
        (
            "allows_series_skill_assignment",
            skill_definition("skill:weapon", SkillKind.WEAPON),
        ),
        (
            "allows_group_skill_assignment",
            skill_definition("skill:armor", SkillKind.ARMOR),
        ),
        (
            "allows_group_skill_assignment",
            skill_definition("skill:weapon", SkillKind.WEAPON),
        ),
    ],
)
def test_catalog_unrelated_skill_kinds_do_not_satisfy_assignment_availability(
    field_name: str,
    unrelated_skill: SkillDefinition,
) -> None:
    assignments = {field_name: True}
    equipment_item = EquipmentDefinition(
        equipment_id="equipment:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(),
        slots=(),
        **assignments,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match=field_name):
        catalog(
            equipment_items=(equipment_item,),
            skill_items=(unrelated_skill,),
        )


@pytest.mark.parametrize(
    ("field_name", "missing_skill_id"),
    [
        ("series_skill_id", "skill:missing-series"),
        ("group_skill_id", "skill:missing-group"),
    ],
)
def test_catalog_rejects_missing_membership_reference(
    field_name: str,
    missing_skill_id: str,
) -> None:
    memberships = {field_name: missing_skill_id}
    equipment_item = EquipmentDefinition(
        equipment_id="equipment:weapon:training-blade",
        part=EquipmentPart.WEAPON,
        skills=(skill(),),
        slots=(weapon_slot(),),
        **memberships,  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError) as exc_info:
        catalog(equipment_items=(equipment_item,), skill_items=())

    assert "equipment" in str(exc_info.value)
    assert field_name in str(exc_info.value)


@pytest.mark.parametrize(
    "wrong_skill",
    [
        skill_definition("skill:armor", SkillKind.ARMOR),
        skill_definition("skill:weapon", SkillKind.WEAPON),
        group_skill_definition("skill:group"),
    ],
)
def test_catalog_rejects_series_reference_to_wrong_kind(
    wrong_skill: SkillDefinition,
) -> None:
    equipment_item = equipment(series_skill_id=wrong_skill.skill_id)

    with pytest.raises(ValueError) as exc_info:
        catalog(
            equipment_items=(equipment_item,),
            skill_items=(wrong_skill,),
        )

    assert "equipment" in str(exc_info.value)
    assert "series_skill_id" in str(exc_info.value)


@pytest.mark.parametrize(
    "wrong_skill",
    [
        skill_definition("skill:armor", SkillKind.ARMOR),
        skill_definition("skill:weapon", SkillKind.WEAPON),
        series_skill_definition("skill:series"),
    ],
)
def test_catalog_rejects_group_reference_to_wrong_kind(
    wrong_skill: SkillDefinition,
) -> None:
    equipment_item = equipment(group_skill_id=wrong_skill.skill_id)

    with pytest.raises(ValueError) as exc_info:
        catalog(
            equipment_items=(equipment_item,),
            skill_items=(wrong_skill,),
        )

    assert "equipment" in str(exc_info.value)
    assert "group_skill_id" in str(exc_info.value)


def test_catalog_with_memberships_remains_frozen_and_hashable() -> None:
    series_skill = series_skill_definition()
    group_skill = group_skill_definition()
    created = catalog(
        equipment_items=(
            equipment(
                series_skill_id=series_skill.skill_id,
                group_skill_id=group_skill.skill_id,
            ),
        ),
        skill_items=(series_skill, group_skill),
    )

    assert hash(created) == hash(
        catalog(
            equipment_items=(
                equipment(
                    series_skill_id=series_skill.skill_id,
                    group_skill_id=group_skill.skill_id,
                ),
            ),
            skill_items=(series_skill, group_skill),
        )
    )
    with pytest.raises(FrozenInstanceError):
        created.equipment = ()


def test_catalog_accepts_ordered_skill_definitions() -> None:
    skill_items = (
        skill_definition("skill:attack-boost"),
        skill_definition("skill:critical-eye"),
        skill_definition(
            "skill:series-bonus",
            SkillKind.SERIES,
            (SkillRankDefinition(1, 2), SkillRankDefinition(2, 4)),
        ),
    )

    created = catalog(skill_items=skill_items)

    assert created.skills == skill_items


def test_catalog_preserves_schema_version_one() -> None:
    assert catalog(schema_version=1).schema_version == 1


def test_catalog_accepts_large_positive_schema_version() -> None:
    assert catalog(schema_version=999).schema_version == 999


def test_catalog_preserves_equipment_order() -> None:
    equipment_items = (
        equipment("equipment:weapon:training-blade"),
        equipment("equipment:head:precision-alpha"),
    )

    assert catalog(equipment_items=equipment_items).equipment == equipment_items


def test_catalog_preserves_decoration_order() -> None:
    decoration_items = (
        decoration("decoration:weapon-power-1"),
        decoration("decoration:armor-power-1"),
    )

    assert catalog(decoration_items=decoration_items).decorations == decoration_items


def test_catalogs_with_same_values_are_equal() -> None:
    assert catalog() == catalog()


@pytest.mark.parametrize(
    "other",
    [
        catalog(schema_version=2),
        catalog(equipment_items=(equipment("equipment:head:precision-alpha"),)),
        catalog(decoration_items=(decoration("decoration:armor-power-1"),)),
    ],
)
def test_catalogs_with_different_values_are_not_equal(other: Catalog) -> None:
    assert catalog() != other


def test_catalog_is_hashable() -> None:
    assert hash(catalog()) == hash(catalog())


def test_catalog_with_skills_is_hashable_and_compares_by_value() -> None:
    skill_items = (skill_definition(),)

    assert catalog(skill_items=skill_items) == catalog(skill_items=skill_items)
    assert hash(catalog(skill_items=skill_items)) == hash(
        catalog(skill_items=skill_items)
    )


def test_catalog_fields_cannot_be_reassigned() -> None:
    created = catalog()

    with pytest.raises(FrozenInstanceError):
        created.schema_version = 2


def test_catalog_skills_cannot_be_reassigned() -> None:
    created = catalog(skill_items=(skill_definition(),))

    with pytest.raises(FrozenInstanceError):
        created.skills = ()


@pytest.mark.parametrize("schema_version", [0, -1])
def test_catalog_rejects_non_positive_schema_version(schema_version: int) -> None:
    with pytest.raises(ValueError, match="schema_version"):
        catalog(schema_version=schema_version)


def test_catalog_rejects_bool_schema_version() -> None:
    with pytest.raises(TypeError, match="schema_version"):
        Catalog(
            schema_version=True,  # type: ignore[arg-type]
            equipment=(),
            decorations=(),
        )


@pytest.mark.parametrize("schema_version", [1.5, "1", None])
def test_catalog_rejects_non_int_schema_version(schema_version: object) -> None:
    with pytest.raises(TypeError, match="schema_version"):
        Catalog(
            schema_version=schema_version,  # type: ignore[arg-type]
            equipment=(),
            decorations=(),
        )


def equipment_generator() -> Iterator[EquipmentDefinition]:
    yield equipment()


@pytest.mark.parametrize(
    "equipment_items",
    [
        [equipment()],
        {equipment()},
        equipment_generator(),
    ],
)
def test_catalog_rejects_non_tuple_equipment(equipment_items: object) -> None:
    with pytest.raises(TypeError, match="equipment"):
        Catalog(
            schema_version=1,
            equipment=equipment_items,  # type: ignore[arg-type]
            decorations=(),
        )


@pytest.mark.parametrize("invalid_equipment", ["equipment", None])
def test_catalog_rejects_invalid_equipment_elements(
    invalid_equipment: object,
) -> None:
    with pytest.raises(TypeError, match="equipment"):
        Catalog(
            schema_version=1,
            equipment=(invalid_equipment,),  # type: ignore[arg-type]
            decorations=(),
        )


def test_catalog_accepts_empty_equipment_tuple() -> None:
    assert catalog(equipment_items=()).equipment == ()


@pytest.mark.parametrize(
    "equipment_items",
    [
        (
            equipment("equipment:weapon:training-blade"),
            equipment("equipment:weapon:training-blade"),
        ),
        (
            equipment("equipment:weapon:training-blade", skills=(skill("skill:a", 1),)),
            equipment("equipment:weapon:training-blade", skills=(skill("skill:b", 1),)),
        ),
    ],
)
def test_catalog_rejects_duplicate_equipment_ids(
    equipment_items: tuple[EquipmentDefinition, ...],
) -> None:
    with pytest.raises(ValueError, match="equipment"):
        catalog(equipment_items=equipment_items)


def test_catalog_accepts_multiple_different_equipment_ids() -> None:
    equipment_items = (
        equipment("equipment:weapon:training-blade"),
        equipment("equipment:head:precision-alpha"),
    )

    assert catalog(equipment_items=equipment_items).equipment == equipment_items


def decoration_generator() -> Iterator[DecorationDefinition]:
    yield decoration()


@pytest.mark.parametrize(
    "decoration_items",
    [
        [decoration()],
        {decoration()},
        decoration_generator(),
    ],
)
def test_catalog_rejects_non_tuple_decorations(decoration_items: object) -> None:
    with pytest.raises(TypeError, match="decorations"):
        Catalog(
            schema_version=1,
            equipment=(),
            decorations=decoration_items,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_decoration", ["decoration", None])
def test_catalog_rejects_invalid_decoration_elements(
    invalid_decoration: object,
) -> None:
    with pytest.raises(TypeError, match="decorations"):
        Catalog(
            schema_version=1,
            equipment=(),
            decorations=(invalid_decoration,),  # type: ignore[arg-type]
        )


def test_catalog_accepts_empty_decorations_tuple() -> None:
    assert catalog(decoration_items=()).decorations == ()


@pytest.mark.parametrize(
    "decoration_items",
    [
        (
            decoration("decoration:weapon-power-1"),
            decoration("decoration:weapon-power-1"),
        ),
        (
            decoration("decoration:weapon-power-1", skills=(skill("skill:a", 1),)),
            decoration("decoration:weapon-power-1", skills=(skill("skill:b", 1),)),
        ),
    ],
)
def test_catalog_rejects_duplicate_decoration_ids(
    decoration_items: tuple[DecorationDefinition, ...],
) -> None:
    with pytest.raises(ValueError, match="decorations"):
        catalog(decoration_items=decoration_items)


def test_catalog_accepts_multiple_different_decoration_ids() -> None:
    decoration_items = (
        decoration("decoration:weapon-power-1"),
        decoration("decoration:armor-power-1"),
    )

    assert catalog(decoration_items=decoration_items).decorations == decoration_items


def skill_definition_generator() -> Iterator[SkillDefinition]:
    yield skill_definition()


@pytest.mark.parametrize(
    "skill_items",
    [
        [skill_definition()],
        {skill_definition()},
        skill_definition_generator(),
    ],
)
def test_catalog_rejects_non_tuple_skills(skill_items: object) -> None:
    with pytest.raises(TypeError, match="skills"):
        Catalog(
            schema_version=1,
            equipment=(),
            decorations=(),
            skills=skill_items,  # type: ignore[arg-type]
        )


def test_catalog_rejects_skill_tuple_subclass() -> None:
    class SkillTuple(tuple[SkillDefinition, ...]):
        pass

    with pytest.raises(TypeError, match="skills"):
        Catalog(
            schema_version=1,
            equipment=(),
            decorations=(),
            skills=SkillTuple((skill_definition(),)),
        )


@pytest.mark.parametrize("invalid_skill", ["skill", None, 1])
def test_catalog_rejects_invalid_skill_elements(invalid_skill: object) -> None:
    with pytest.raises(TypeError, match="skills"):
        Catalog(
            schema_version=1,
            equipment=(),
            decorations=(),
            skills=(invalid_skill,),  # type: ignore[arg-type]
        )


def test_catalog_accepts_empty_skills_tuple() -> None:
    assert catalog(skill_items=()).skills == ()


def test_catalog_rejects_duplicate_skill_ids() -> None:
    skill_items = (
        skill_definition("skill:attack-boost"),
        skill_definition(
            "skill:attack-boost",
            SkillKind.WEAPON,
            (SkillRankDefinition(1, None),),
        ),
    )

    with pytest.raises(ValueError, match="skills"):
        catalog(skill_items=skill_items)


def test_catalog_allows_same_id_across_equipment_and_decoration_namespaces() -> None:
    shared_id = "shared:id"

    created = Catalog(
        schema_version=1,
        equipment=(equipment(shared_id),),
        decorations=(decoration(shared_id),),
    )

    assert created.equipment[0].equipment_id == shared_id
    assert created.decorations[0].decoration_id == shared_id


def test_catalog_package_exports_catalog() -> None:
    from mhwilds_skill_sim.catalog import Catalog as ExportedCatalog

    assert ExportedCatalog is Catalog


def test_legacy_catalog_defaults_appraisal_rule_fields_to_empty_tuples() -> None:
    created = Catalog(schema_version=1, equipment=(), decorations=())

    assert created.appraisal_charm_skill_groups == ()
    assert created.appraisal_charm_patterns == ()


def test_catalog_accepts_ordered_appraisal_groups_and_patterns() -> None:
    skills = (
        skill_definition("skill:attack-boost", SkillKind.ARMOR),
        skill_definition("skill:weapon-technique", SkillKind.WEAPON),
    )
    groups = (
        appraisal_skill_group(
            "appraisal-group:B",
            (skill("skill:weapon-technique"),),
        ),
        appraisal_skill_group(
            "appraisal-group:A",
            (skill("skill:attack-boost"),),
        ),
    )
    patterns = (
        appraisal_pattern(
            "appraisal-pattern:r8-b-a",
            ("appraisal-group:B", "appraisal-group:A"),
            slots=(weapon_slot(), armor_slot()),
        ),
        appraisal_pattern(
            "appraisal-pattern:r7-a",
            ("appraisal-group:A",),
            rarity=7,
            slots=(armor_slot(2),),
        ),
    )

    created = catalog(
        skill_items=skills,
        appraisal_group_items=groups,
        appraisal_pattern_items=patterns,
    )

    assert created.appraisal_charm_skill_groups == groups
    assert created.appraisal_charm_patterns == patterns


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("appraisal_charm_skill_groups", []),
        ("appraisal_charm_skill_groups", set()),
        ("appraisal_charm_patterns", []),
        ("appraisal_charm_patterns", set()),
    ],
)
def test_catalog_rejects_non_tuple_appraisal_rule_fields(
    field_name: str,
    invalid_value: object,
) -> None:
    values = {
        "schema_version": 1,
        "equipment": (),
        "decorations": (),
        field_name: invalid_value,
    }

    with pytest.raises(TypeError, match=field_name):
        Catalog(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    ["appraisal_charm_skill_groups", "appraisal_charm_patterns"],
)
def test_catalog_rejects_appraisal_rule_tuple_subclasses(field_name: str) -> None:
    class RuleTuple(tuple[object, ...]):
        pass

    values = {
        "schema_version": 1,
        "equipment": (),
        "decorations": (),
        field_name: RuleTuple(),
    }

    with pytest.raises(TypeError, match=field_name):
        Catalog(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("appraisal_charm_skill_groups", "group"),
        ("appraisal_charm_skill_groups", None),
        ("appraisal_charm_patterns", "pattern"),
        ("appraisal_charm_patterns", None),
    ],
)
def test_catalog_rejects_invalid_appraisal_rule_items(
    field_name: str,
    invalid_value: object,
) -> None:
    values = {
        "schema_version": 1,
        "equipment": (),
        "decorations": (),
        field_name: (invalid_value,),
    }

    with pytest.raises(TypeError, match=field_name):
        Catalog(**values)  # type: ignore[arg-type]


def test_catalog_rejects_duplicate_appraisal_group_ids() -> None:
    groups = (
        appraisal_skill_group(),
        appraisal_skill_group(skills=(skill("skill:critical-eye"),)),
    )

    with pytest.raises(ValueError, match="appraisal_charm_skill_groups"):
        catalog(appraisal_group_items=groups)


def test_catalog_rejects_duplicate_appraisal_pattern_ids() -> None:
    groups = (appraisal_skill_group(),)
    patterns = (
        appraisal_pattern(),
        appraisal_pattern(skill_group_ids=("appraisal-group:A",) * 2),
    )

    with pytest.raises(ValueError, match="appraisal_charm_patterns"):
        catalog(
            skill_items=(skill_definition(),),
            appraisal_group_items=groups,
            appraisal_pattern_items=patterns,
        )


@pytest.mark.parametrize("kind", [SkillKind.ARMOR, SkillKind.WEAPON])
def test_catalog_accepts_appraisal_group_armor_and_weapon_skill_references(
    kind: SkillKind,
) -> None:
    skill_id = f"skill:{kind.value}-technique"
    group = appraisal_skill_group(skills=(skill(skill_id),))

    created = catalog(
        skill_items=(skill_definition(skill_id, kind),),
        appraisal_group_items=(group,),
    )

    assert created.appraisal_charm_skill_groups == (group,)


def test_catalog_rejects_missing_appraisal_group_skill_reference() -> None:
    group = appraisal_skill_group(skills=(skill("skill:missing"),))

    with pytest.raises(ValueError) as exc_info:
        catalog(appraisal_group_items=(group,))

    assert "appraisal_charm_skill_groups" in str(exc_info.value)
    assert "existing" in str(exc_info.value)


@pytest.mark.parametrize(
    "invalid_skill",
    [series_skill_definition(), group_skill_definition()],
)
def test_catalog_rejects_appraisal_group_bonus_skill_kinds(
    invalid_skill: SkillDefinition,
) -> None:
    group = appraisal_skill_group(skills=(skill(invalid_skill.skill_id),))

    with pytest.raises(ValueError) as exc_info:
        catalog(
            skill_items=(invalid_skill,),
            appraisal_group_items=(group,),
        )

    assert "appraisal_charm_skill_groups" in str(exc_info.value)
    assert "armor or weapon" in str(exc_info.value)


def test_catalog_rejects_appraisal_group_level_above_maximum_rank() -> None:
    group = appraisal_skill_group(skills=(skill(level=2),))

    with pytest.raises(ValueError) as exc_info:
        catalog(
            skill_items=(skill_definition(),),
            appraisal_group_items=(group,),
        )

    assert "appraisal_charm_skill_groups" in str(exc_info.value)
    assert "level" in str(exc_info.value)
    assert "maximum" in str(exc_info.value)


def test_catalog_accepts_existing_and_repeated_pattern_group_references() -> None:
    group = appraisal_skill_group()
    charm_pattern = appraisal_pattern(
        skill_group_ids=("appraisal-group:A", "appraisal-group:A"),
    )

    created = catalog(
        skill_items=(skill_definition(),),
        appraisal_group_items=(group,),
        appraisal_pattern_items=(charm_pattern,),
    )

    assert created.appraisal_charm_patterns[0].skill_group_ids == (
        "appraisal-group:A",
        "appraisal-group:A",
    )


def test_catalog_rejects_missing_pattern_group_reference() -> None:
    charm_pattern = appraisal_pattern(skill_group_ids=("appraisal-group:missing",))

    with pytest.raises(ValueError) as exc_info:
        catalog(appraisal_pattern_items=(charm_pattern,))

    assert "appraisal_charm_patterns" in str(exc_info.value)
    assert "skill_group_ids" in str(exc_info.value)


def test_catalog_allows_unused_appraisal_group_and_unused_skill() -> None:
    metadata = (
        skill_definition("skill:attack-boost"),
        skill_definition("skill:unused"),
    )
    group = appraisal_skill_group()

    created = catalog(
        skill_items=metadata,
        appraisal_group_items=(group,),
        appraisal_pattern_items=(),
    )

    assert created.skills == metadata
    assert created.appraisal_charm_skill_groups == (group,)
    assert created.appraisal_charm_patterns == ()


def test_catalog_with_appraisal_rules_is_frozen_hashable_and_value_based() -> None:
    groups = (appraisal_skill_group(),)
    patterns = (appraisal_pattern(),)
    first = catalog(
        skill_items=(skill_definition(),),
        appraisal_group_items=groups,
        appraisal_pattern_items=patterns,
    )
    second = catalog(
        skill_items=(skill_definition(),),
        appraisal_group_items=groups,
        appraisal_pattern_items=patterns,
    )

    assert first == second
    assert hash(first) == hash(second)
    with pytest.raises(FrozenInstanceError):
        first.appraisal_charm_patterns = ()
