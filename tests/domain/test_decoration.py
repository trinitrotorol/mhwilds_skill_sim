from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain import (
    DecorationDefinition,
    DecorationKind,
    DecorationSlot,
    SkillContribution,
    can_place_decoration,
)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def decoration(
    decoration_id: str = "decoration:attack-jewel-1",
    required_slot: DecorationSlot | None = None,
    skills: tuple[SkillContribution, ...] | None = None,
) -> DecorationDefinition:
    return DecorationDefinition(
        decoration_id=decoration_id,
        required_slot=required_slot or weapon_slot(1),
        skills=skills or (skill(),),
    )


def test_can_create_weapon_decoration_definition_with_one_skill() -> None:
    definition = DecorationDefinition(
        decoration_id="decoration:attack-jewel-1",
        required_slot=weapon_slot(1),
        skills=(skill("skill:attack-boost", 1),),
    )

    assert definition.decoration_id == "decoration:attack-jewel-1"
    assert definition.required_slot == weapon_slot(1)
    assert definition.skills == (skill("skill:attack-boost", 1),)


def test_can_create_armor_decoration_definition_with_multiple_skills() -> None:
    skills = (
        skill("skill:critical-eye", 1),
        skill("skill:weakness-exploit", 2),
    )

    definition = DecorationDefinition(
        decoration_id="decoration:expert-tenderizer-jewel-4",
        required_slot=armor_slot(4),
        skills=skills,
    )

    assert definition.required_slot == armor_slot(4)
    assert definition.skills == skills


@pytest.mark.parametrize(
    "decoration_id",
    [
        "decoration:venom-jewel-1",
        "wilds:decoration:-2144349312",
        "Decoration:Internal_ID-01",
    ],
)
def test_decoration_definition_preserves_decoration_id_without_normalization(
    decoration_id: str,
) -> None:
    definition = decoration(decoration_id=decoration_id)

    assert definition.decoration_id == decoration_id


def test_decoration_definition_preserves_skill_order() -> None:
    skills = (
        skill("skill:attack-boost", 1),
        skill("skill:critical-eye", 2),
    )

    definition = decoration(skills=skills)

    assert definition.skills == skills


def test_decoration_definitions_with_same_values_are_equal() -> None:
    assert decoration() == decoration()


@pytest.mark.parametrize(
    "other",
    [
        decoration(decoration_id="decoration:critical-jewel-2"),
        decoration(required_slot=armor_slot(1)),
        decoration(skills=(skill("skill:critical-eye", 1),)),
    ],
)
def test_decoration_definitions_with_different_values_are_not_equal(
    other: DecorationDefinition,
) -> None:
    assert decoration() != other


def test_decoration_definition_is_hashable() -> None:
    assert hash(decoration()) == hash(decoration())


def test_decoration_definition_fields_cannot_be_reassigned() -> None:
    definition = decoration()

    with pytest.raises(FrozenInstanceError):
        definition.decoration_id = "decoration:other"


@pytest.mark.parametrize("decoration_id", ["", " ", "\t\n"])
def test_decoration_definition_rejects_empty_or_blank_decoration_id(
    decoration_id: str,
) -> None:
    with pytest.raises(ValueError, match="decoration_id"):
        decoration(decoration_id=decoration_id)


@pytest.mark.parametrize(
    "decoration_id",
    [" decoration:venom-jewel-1", "\tdecoration:venom-jewel-1"],
)
def test_decoration_definition_rejects_leading_whitespace_decoration_id(
    decoration_id: str,
) -> None:
    with pytest.raises(ValueError, match="decoration_id"):
        decoration(decoration_id=decoration_id)


@pytest.mark.parametrize(
    "decoration_id",
    ["decoration:venom-jewel-1 ", "decoration:venom-jewel-1\n"],
)
def test_decoration_definition_rejects_trailing_whitespace_decoration_id(
    decoration_id: str,
) -> None:
    with pytest.raises(ValueError, match="decoration_id"):
        decoration(decoration_id=decoration_id)


@pytest.mark.parametrize("decoration_id", [1, None])
def test_decoration_definition_rejects_non_str_decoration_id(
    decoration_id: object,
) -> None:
    with pytest.raises(TypeError, match="decoration_id"):
        decoration(decoration_id=decoration_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("required_slot", ["weapon", None])
def test_decoration_definition_rejects_invalid_required_slot(
    required_slot: object,
) -> None:
    with pytest.raises(TypeError, match="required_slot"):
        DecorationDefinition(
            decoration_id="decoration:attack-jewel-1",
            required_slot=required_slot,  # type: ignore[arg-type]
            skills=(skill(),),
        )


def test_decoration_definition_rejects_empty_skills() -> None:
    with pytest.raises(ValueError, match="skills"):
        DecorationDefinition(
            decoration_id="decoration:attack-jewel-1",
            required_slot=weapon_slot(1),
            skills=(),
        )


def skill_generator() -> Iterator[SkillContribution]:
    yield skill()


@pytest.mark.parametrize(
    "skills",
    [
        [skill()],
        {skill()},
        skill_generator(),
    ],
)
def test_decoration_definition_rejects_non_tuple_skills(skills: object) -> None:
    with pytest.raises(TypeError, match="skills"):
        DecorationDefinition(
            decoration_id="decoration:attack-jewel-1",
            required_slot=weapon_slot(1),
            skills=skills,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_skill", ["skill:attack-boost", None])
def test_decoration_definition_rejects_invalid_skill_elements(
    invalid_skill: object,
) -> None:
    with pytest.raises(TypeError, match="skills"):
        DecorationDefinition(
            decoration_id="decoration:attack-jewel-1",
            required_slot=weapon_slot(1),
            skills=(invalid_skill,),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "skills",
    [
        (
            skill("skill:attack-boost", 1),
            skill("skill:attack-boost", 1),
        ),
        (
            skill("skill:attack-boost", 1),
            skill("skill:attack-boost", 2),
        ),
    ],
)
def test_decoration_definition_rejects_duplicate_skill_ids(
    skills: tuple[SkillContribution, ...],
) -> None:
    with pytest.raises(ValueError, match="skills"):
        decoration(skills=skills)


def test_decoration_definition_accepts_multiple_different_skill_ids() -> None:
    skills = (
        skill("skill:attack-boost", 1),
        skill("skill:critical-eye", 1),
    )

    definition = decoration(skills=skills)

    assert definition.skills == skills


def test_domain_package_exports_decoration_definition() -> None:
    from mhwilds_skill_sim.domain import (
        DecorationDefinition as ExportedDecorationDefinition,
    )

    assert ExportedDecorationDefinition is DecorationDefinition


def test_domain_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.domain import (
        DecorationKind as ExportedDecorationKind,
        DecorationSlot as ExportedDecorationSlot,
        SkillContribution as ExportedSkillContribution,
        can_place_decoration as exported_can_place_decoration,
    )

    assert ExportedDecorationKind is DecorationKind
    assert ExportedDecorationSlot is DecorationSlot
    assert ExportedSkillContribution is SkillContribution
    assert exported_can_place_decoration is can_place_decoration
