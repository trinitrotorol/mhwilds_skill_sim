from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.catalog import Catalog
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
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=EquipmentPart.WEAPON,
        skills=skills if skills is not None else (skill(),),
        slots=slots if slots is not None else (weapon_slot(1),),
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


def catalog(
    schema_version: int = 1,
    equipment_items: tuple[EquipmentDefinition, ...] | None = None,
    decoration_items: tuple[DecorationDefinition, ...] | None = None,
    skill_items: tuple[SkillDefinition, ...] | None = None,
) -> Catalog:
    return Catalog(
        schema_version=schema_version,
        equipment=equipment_items if equipment_items is not None else (equipment(),),
        decorations=(
            decoration_items if decoration_items is not None else (decoration(),)
        ),
        skills=skill_items if skill_items is not None else (),
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
