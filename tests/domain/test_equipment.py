from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain import (
    DecorationDefinition,
    DecorationKind,
    DecorationSlot,
    EquipmentDefinition,
    EquipmentPart,
    SkillContribution,
    WeaponKind,
    can_place_decoration,
)


EXPECTED_EQUIPMENT_PARTS = [
    EquipmentPart.WEAPON,
    EquipmentPart.HEAD,
    EquipmentPart.CHEST,
    EquipmentPart.ARMS,
    EquipmentPart.WAIST,
    EquipmentPart.LEGS,
    EquipmentPart.CHARM,
]

EXPECTED_EQUIPMENT_PART_VALUES = [
    "weapon",
    "head",
    "chest",
    "arms",
    "waist",
    "legs",
    "charm",
]

EXPECTED_WEAPON_KINDS = [
    WeaponKind.BOW,
    WeaponKind.CHARGE_BLADE,
    WeaponKind.DUAL_BLADES,
    WeaponKind.GREAT_SWORD,
    WeaponKind.GUNLANCE,
    WeaponKind.HAMMER,
    WeaponKind.HEAVY_BOWGUN,
    WeaponKind.HUNTING_HORN,
    WeaponKind.INSECT_GLAIVE,
    WeaponKind.LANCE,
    WeaponKind.LIGHT_BOWGUN,
    WeaponKind.LONG_SWORD,
    WeaponKind.SWITCH_AXE,
    WeaponKind.SWORD_SHIELD,
]

EXPECTED_WEAPON_KIND_NAMES = [
    "BOW",
    "CHARGE_BLADE",
    "DUAL_BLADES",
    "GREAT_SWORD",
    "GUNLANCE",
    "HAMMER",
    "HEAVY_BOWGUN",
    "HUNTING_HORN",
    "INSECT_GLAIVE",
    "LANCE",
    "LIGHT_BOWGUN",
    "LONG_SWORD",
    "SWITCH_AXE",
    "SWORD_SHIELD",
]

EXPECTED_WEAPON_KIND_VALUES = [
    "bow",
    "charge-blade",
    "dual-blades",
    "great-sword",
    "gunlance",
    "hammer",
    "heavy-bowgun",
    "hunting-horn",
    "insect-glaive",
    "lance",
    "light-bowgun",
    "long-sword",
    "switch-axe",
    "sword-shield",
]


def skill(skill_id: str = "skill:attack-boost", level: int = 1) -> SkillContribution:
    return SkillContribution(skill_id, level)


def weapon_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.WEAPON, level)


def armor_slot(level: int = 1) -> DecorationSlot:
    return DecorationSlot(DecorationKind.ARMOR, level)


def equipment(
    equipment_id: str = "weapon:great-sword:hope-blade",
    part: EquipmentPart = EquipmentPart.WEAPON,
    skills: tuple[SkillContribution, ...] | None = None,
    slots: tuple[DecorationSlot, ...] | None = None,
    series_skill_id: str | None = None,
    group_skill_id: str | None = None,
    allows_series_skill_assignment: bool = False,
    allows_group_skill_assignment: bool = False,
    display_name: str | None = None,
    weapon_kind: WeaponKind | None = None,
    additional_series_skill_ids: tuple[str, ...] = (),
    additional_group_skill_ids: tuple[str, ...] = (),
) -> EquipmentDefinition:
    return EquipmentDefinition(
        equipment_id=equipment_id,
        part=part,
        skills=skills if skills is not None else (skill(),),
        slots=slots if slots is not None else (weapon_slot(1),),
        series_skill_id=series_skill_id,
        group_skill_id=group_skill_id,
        allows_series_skill_assignment=allows_series_skill_assignment,
        allows_group_skill_assignment=allows_group_skill_assignment,
        display_name=display_name,
        weapon_kind=weapon_kind,
        additional_series_skill_ids=additional_series_skill_ids,
        additional_group_skill_ids=additional_group_skill_ids,
    )


def equipment_with_membership_value(
    *,
    field_name: str,
    value: object,
) -> EquipmentDefinition:
    memberships: dict[str, object] = {
        "series_skill_id": None,
        "group_skill_id": None,
    }
    memberships[field_name] = value
    return EquipmentDefinition(
        equipment_id="weapon:great-sword:hope-blade",
        part=EquipmentPart.WEAPON,
        skills=(skill(),),
        slots=(weapon_slot(1),),
        **memberships,  # type: ignore[arg-type]
    )


def equipment_with_assignment_value(
    *,
    field_name: str,
    value: object,
    part: EquipmentPart = EquipmentPart.WEAPON,
) -> EquipmentDefinition:
    assignments: dict[str, object] = {
        "allows_series_skill_assignment": False,
        "allows_group_skill_assignment": False,
    }
    assignments[field_name] = value
    return EquipmentDefinition(
        equipment_id=f"equipment:{part.value}",
        part=part,
        skills=(),
        slots=(),
        **assignments,  # type: ignore[arg-type]
    )


def equipment_with_additional_membership_value(
    *,
    field_name: str,
    value: object,
) -> EquipmentDefinition:
    memberships: dict[str, object] = {
        "additional_series_skill_ids": (),
        "additional_group_skill_ids": (),
    }
    memberships[field_name] = value
    return EquipmentDefinition(
        equipment_id="weapon:great-sword:hope-blade",
        part=EquipmentPart.WEAPON,
        skills=(skill(),),
        slots=(weapon_slot(1),),
        **memberships,  # type: ignore[arg-type]
    )


def test_equipment_part_declaration_order_matches_public_contract() -> None:
    assert list(EquipmentPart) == EXPECTED_EQUIPMENT_PARTS


def test_equipment_part_values_match_public_contract() -> None:
    assert [part.value for part in EquipmentPart] == EXPECTED_EQUIPMENT_PART_VALUES


def test_equipment_part_values_are_unique() -> None:
    values = [part.value for part in EquipmentPart]

    assert len(values) == len(set(values))


@pytest.mark.parametrize("value", EXPECTED_EQUIPMENT_PART_VALUES)
def test_equipment_part_can_be_created_from_valid_strings(value: str) -> None:
    assert EquipmentPart(value).value == value


def test_equipment_part_str_is_stable_value() -> None:
    assert str(EquipmentPart.WEAPON) == "weapon"


@pytest.mark.parametrize("value", ["body", "helm", "Weapon", ""])
def test_equipment_part_rejects_undefined_values(value: str) -> None:
    with pytest.raises(ValueError):
        EquipmentPart(value)


def test_domain_package_exports_equipment_part() -> None:
    from mhwilds_skill_sim.domain import EquipmentPart as ExportedEquipmentPart

    assert ExportedEquipmentPart is EquipmentPart


def test_domain_package_keeps_existing_public_exports() -> None:
    from mhwilds_skill_sim.domain import (
        DecorationDefinition as ExportedDecorationDefinition,
        DecorationKind as ExportedDecorationKind,
        DecorationSlot as ExportedDecorationSlot,
        SkillContribution as ExportedSkillContribution,
        can_place_decoration as exported_can_place_decoration,
    )

    assert ExportedDecorationDefinition is DecorationDefinition
    assert ExportedDecorationKind is DecorationKind
    assert ExportedDecorationSlot is DecorationSlot
    assert ExportedSkillContribution is SkillContribution
    assert exported_can_place_decoration is can_place_decoration


def test_can_create_weapon_equipment_definition_with_skills_and_slots() -> None:
    definition = EquipmentDefinition(
        equipment_id="weapon:great-sword:hope-blade",
        part=EquipmentPart.WEAPON,
        skills=(skill("skill:attack-boost", 1),),
        slots=(weapon_slot(1), weapon_slot(2)),
    )

    assert definition.equipment_id == "weapon:great-sword:hope-blade"
    assert definition.part is EquipmentPart.WEAPON
    assert definition.skills == (skill("skill:attack-boost", 1),)
    assert definition.slots == (weapon_slot(1), weapon_slot(2))
    assert definition.series_skill_id is None
    assert definition.group_skill_id is None
    assert definition.allows_series_skill_assignment is False
    assert definition.allows_group_skill_assignment is False


def test_can_create_armor_equipment_definition_with_skills_and_slots() -> None:
    definition = EquipmentDefinition(
        equipment_id="armor:head:hope-mask",
        part=EquipmentPart.HEAD,
        skills=(skill("skill:critical-eye", 1),),
        slots=(armor_slot(2),),
    )

    assert definition.equipment_id == "armor:head:hope-mask"
    assert definition.part is EquipmentPart.HEAD
    assert definition.skills == (skill("skill:critical-eye", 1),)
    assert definition.slots == (armor_slot(2),)


def test_can_create_equipment_definition_without_skills_or_slots() -> None:
    definition = equipment(skills=(), slots=())

    assert definition.skills == ()
    assert definition.slots == ()


def test_legacy_four_argument_equipment_construction_defaults_memberships() -> None:
    definition = EquipmentDefinition(
        "weapon:great-sword:hope-blade",
        EquipmentPart.WEAPON,
        (skill(),),
        (weapon_slot(),),
    )

    assert definition.series_skill_id is None
    assert definition.group_skill_id is None
    assert definition.allows_series_skill_assignment is False
    assert definition.allows_group_skill_assignment is False


def test_equipment_definition_accepts_series_assignment_capable_weapon() -> None:
    definition = equipment(allows_series_skill_assignment=True)

    assert definition.allows_series_skill_assignment is True
    assert definition.allows_group_skill_assignment is False


def test_equipment_definition_accepts_group_assignment_capable_weapon() -> None:
    definition = equipment(allows_group_skill_assignment=True)

    assert definition.allows_series_skill_assignment is False
    assert definition.allows_group_skill_assignment is True


def test_equipment_definition_accepts_dual_assignment_capable_weapon() -> None:
    definition = equipment(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )

    assert definition.allows_series_skill_assignment is True
    assert definition.allows_group_skill_assignment is True


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
@pytest.mark.parametrize("value", [0, 1, "true", None, [], object()])
def test_equipment_definition_rejects_non_bool_assignment_flags(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match=field_name):
        equipment_with_assignment_value(field_name=field_name, value=value)


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
@pytest.mark.parametrize(
    "part",
    [
        EquipmentPart.HEAD,
        EquipmentPart.CHEST,
        EquipmentPart.ARMS,
        EquipmentPart.WAIST,
        EquipmentPart.LEGS,
        EquipmentPart.CHARM,
    ],
)
def test_equipment_definition_rejects_assignment_capability_on_non_weapon(
    field_name: str,
    part: EquipmentPart,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        equipment_with_assignment_value(field_name=field_name, value=True, part=part)


def test_equipment_definition_rejects_fixed_series_and_series_assignment() -> None:
    with pytest.raises(
        ValueError,
        match="allows_series_skill_assignment.*series_skill_id",
    ):
        equipment(
            series_skill_id="skill:series-bonus",
            allows_series_skill_assignment=True,
        )


def test_equipment_definition_rejects_fixed_group_and_group_assignment() -> None:
    with pytest.raises(
        ValueError,
        match="allows_group_skill_assignment.*group_skill_id",
    ):
        equipment(
            group_skill_id="skill:group-bonus",
            allows_group_skill_assignment=True,
        )


def test_fixed_membership_weapon_with_assignment_flags_false_remains_valid() -> None:
    definition = equipment(
        series_skill_id="skill:series-bonus",
        group_skill_id="skill:group-bonus",
    )

    assert definition.series_skill_id == "skill:series-bonus"
    assert definition.group_skill_id == "skill:group-bonus"
    assert definition.allows_series_skill_assignment is False
    assert definition.allows_group_skill_assignment is False


def test_equipment_definition_accepts_series_only_membership() -> None:
    definition = equipment(series_skill_id="skill:fixture-series-bonus")

    assert definition.series_skill_id == "skill:fixture-series-bonus"
    assert definition.group_skill_id is None
    assert definition.skills == (skill(),)


def test_equipment_definition_accepts_group_only_membership() -> None:
    definition = equipment(group_skill_id="skill:fixture-group-bonus")

    assert definition.series_skill_id is None
    assert definition.group_skill_id == "skill:fixture-group-bonus"
    assert definition.skills == (skill(),)


def test_equipment_definition_accepts_both_memberships() -> None:
    definition = equipment(
        series_skill_id="skill:fixture-series-bonus",
        group_skill_id="skill:fixture-group-bonus",
    )

    assert definition.series_skill_id == "skill:fixture-series-bonus"
    assert definition.group_skill_id == "skill:fixture-group-bonus"


@pytest.mark.parametrize(
    ("field_name", "membership_id"),
    [
        ("series_skill_id", "Skill:Series_Internal-ID.01"),
        ("group_skill_id", "Skill:Group_Internal-ID.01"),
    ],
)
def test_equipment_definition_preserves_membership_id_text(
    field_name: str,
    membership_id: str,
) -> None:
    definition = equipment_with_membership_value(
        field_name=field_name,
        value=membership_id,
    )

    assert getattr(definition, field_name) == membership_id


@pytest.mark.parametrize("part", EXPECTED_EQUIPMENT_PARTS)
def test_can_create_equipment_definition_for_every_part(part: EquipmentPart) -> None:
    definition = equipment(part=part)

    assert definition.part is part


@pytest.mark.parametrize(
    "equipment_id",
    [
        "weapon:great-sword:hope-blade",
        "armor:head:hope-mask",
        "charm:challenger-1",
        "wilds:equipment:-2144349312",
        "Equipment:Internal_ID-01",
    ],
)
def test_equipment_definition_preserves_equipment_id_without_normalization(
    equipment_id: str,
) -> None:
    definition = equipment(equipment_id=equipment_id)

    assert definition.equipment_id == equipment_id


def test_equipment_definition_preserves_skill_order() -> None:
    skills = (
        skill("skill:attack-boost", 1),
        skill("skill:critical-eye", 2),
    )

    definition = equipment(skills=skills)

    assert definition.skills == skills


def test_equipment_definition_preserves_slot_order() -> None:
    slots = (armor_slot(1), armor_slot(3), armor_slot(2))

    definition = equipment(slots=slots)

    assert definition.slots == slots


def test_equipment_definitions_with_same_values_are_equal() -> None:
    assert equipment() == equipment()


@pytest.mark.parametrize(
    "other",
    [
        equipment(equipment_id="weapon:great-sword:other"),
        equipment(part=EquipmentPart.HEAD),
        equipment(skills=(skill("skill:critical-eye", 1),)),
        equipment(slots=(weapon_slot(2),)),
        equipment(series_skill_id="skill:fixture-series-bonus"),
        equipment(group_skill_id="skill:fixture-group-bonus"),
        equipment(allows_series_skill_assignment=True),
        equipment(allows_group_skill_assignment=True),
        equipment(weapon_kind=WeaponKind.GREAT_SWORD),
    ],
)
def test_equipment_definitions_with_different_values_are_not_equal(
    other: EquipmentDefinition,
) -> None:
    assert equipment() != other


def test_equipment_definition_is_hashable() -> None:
    assert hash(equipment()) == hash(equipment())


def test_equipment_definition_equality_and_hash_include_memberships() -> None:
    with_memberships = equipment(
        series_skill_id="skill:fixture-series-bonus",
        group_skill_id="skill:fixture-group-bonus",
    )

    assert with_memberships == equipment(
        series_skill_id="skill:fixture-series-bonus",
        group_skill_id="skill:fixture-group-bonus",
    )
    assert hash(with_memberships) == hash(
        equipment(
            series_skill_id="skill:fixture-series-bonus",
            group_skill_id="skill:fixture-group-bonus",
        )
    )
    assert len({equipment(), with_memberships}) == 2


def test_equipment_definition_equality_and_hash_include_assignment_flags() -> None:
    assignment_template = equipment(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )

    assert assignment_template == equipment(
        allows_series_skill_assignment=True,
        allows_group_skill_assignment=True,
    )
    assert hash(assignment_template) == hash(
        equipment(
            allows_series_skill_assignment=True,
            allows_group_skill_assignment=True,
        )
    )
    assert len({equipment(), assignment_template}) == 2


def test_equipment_definition_fields_cannot_be_reassigned() -> None:
    definition = equipment()

    with pytest.raises(FrozenInstanceError):
        definition.equipment_id = "weapon:great-sword:other"


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
def test_equipment_membership_fields_cannot_be_reassigned(field_name: str) -> None:
    definition = equipment()

    with pytest.raises(FrozenInstanceError):
        setattr(definition, field_name, "skill:fixture-bonus")


@pytest.mark.parametrize(
    "field_name",
    ["allows_series_skill_assignment", "allows_group_skill_assignment"],
)
def test_equipment_assignment_flags_cannot_be_reassigned(field_name: str) -> None:
    definition = equipment()

    with pytest.raises(FrozenInstanceError):
        setattr(definition, field_name, True)


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
def test_equipment_definition_accepts_explicit_none_membership(
    field_name: str,
) -> None:
    definition = equipment_with_membership_value(field_name=field_name, value=None)

    assert getattr(definition, field_name) is None


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_equipment_definition_rejects_empty_or_blank_membership_id(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        equipment_with_membership_value(field_name=field_name, value=value)


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
@pytest.mark.parametrize(
    "value",
    [" skill:fixture-bonus", "\tskill:fixture-bonus"],
)
def test_equipment_definition_rejects_leading_whitespace_membership_id(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        equipment_with_membership_value(field_name=field_name, value=value)


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
@pytest.mark.parametrize(
    "value",
    ["skill:fixture-bonus ", "skill:fixture-bonus\n"],
)
def test_equipment_definition_rejects_trailing_whitespace_membership_id(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        equipment_with_membership_value(field_name=field_name, value=value)


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
@pytest.mark.parametrize("value", [True, 1, 1.5, [], object()])
def test_equipment_definition_rejects_non_string_membership_id(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match=field_name):
        equipment_with_membership_value(field_name=field_name, value=value)


@pytest.mark.parametrize("field_name", ["series_skill_id", "group_skill_id"])
def test_equipment_definition_rejects_string_subclass_membership_id(
    field_name: str,
) -> None:
    class MembershipId(str):
        pass

    with pytest.raises(TypeError, match=field_name):
        equipment_with_membership_value(
            field_name=field_name,
            value=MembershipId("skill:fixture-bonus"),
        )


def test_equipment_definition_does_not_look_up_or_classify_memberships() -> None:
    definition = equipment(
        part=EquipmentPart.WEAPON,
        series_skill_id="skill:not-in-a-catalog",
        group_skill_id="skill:not-in-a-catalog",
    )

    assert definition.series_skill_id == "skill:not-in-a-catalog"
    assert definition.group_skill_id == "skill:not-in-a-catalog"


def test_additional_memberships_default_to_empty_tuples() -> None:
    definition = equipment()

    assert definition.additional_series_skill_ids == ()
    assert definition.additional_group_skill_ids == ()
    assert definition.series_skill_ids == ()
    assert definition.group_skill_ids == ()


def test_complete_memberships_put_primary_before_ordered_additional_ids() -> None:
    series_ids = ("skill:series-extra-b", "skill:series-extra-a")
    group_ids = ("skill:group-extra-b", "skill:group-extra-a")

    definition = equipment(
        series_skill_id="skill:series-primary",
        group_skill_id="skill:group-primary",
        additional_series_skill_ids=series_ids,
        additional_group_skill_ids=group_ids,
    )

    assert definition.additional_series_skill_ids is series_ids
    assert definition.additional_group_skill_ids is group_ids
    assert definition.series_skill_ids == (
        "skill:series-primary",
        "skill:series-extra-b",
        "skill:series-extra-a",
    )
    assert definition.group_skill_ids == (
        "skill:group-primary",
        "skill:group-extra-b",
        "skill:group-extra-a",
    )
    assert type(definition.series_skill_ids) is tuple
    assert type(definition.group_skill_ids) is tuple


def test_complete_memberships_support_additional_ids_without_primary() -> None:
    definition = equipment(
        additional_series_skill_ids=("skill:series-extra",),
        additional_group_skill_ids=("skill:group-extra",),
    )

    assert definition.series_skill_ids == ("skill:series-extra",)
    assert definition.group_skill_ids == ("skill:group-extra",)


@pytest.mark.parametrize(
    "field_name",
    ["additional_series_skill_ids", "additional_group_skill_ids"],
)
@pytest.mark.parametrize("value", [[], set(), frozenset(), None])
def test_additional_memberships_reject_non_tuple_values(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match=field_name):
        equipment_with_additional_membership_value(
            field_name=field_name,
            value=value,
        )


@pytest.mark.parametrize(
    "field_name",
    ["additional_series_skill_ids", "additional_group_skill_ids"],
)
def test_additional_memberships_reject_tuple_subclasses(field_name: str) -> None:
    class MembershipTuple(tuple[str, ...]):
        pass

    with pytest.raises(TypeError, match=field_name):
        equipment_with_additional_membership_value(
            field_name=field_name,
            value=MembershipTuple(("skill:bonus",)),
        )


@pytest.mark.parametrize(
    "field_name",
    ["additional_series_skill_ids", "additional_group_skill_ids"],
)
@pytest.mark.parametrize("value", [None, True, 1, object()])
def test_additional_memberships_reject_non_string_elements(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(TypeError, match=field_name):
        equipment_with_additional_membership_value(
            field_name=field_name,
            value=(value,),
        )


@pytest.mark.parametrize(
    "field_name",
    ["additional_series_skill_ids", "additional_group_skill_ids"],
)
def test_additional_memberships_reject_string_subclasses(field_name: str) -> None:
    class MembershipId(str):
        pass

    with pytest.raises(TypeError, match=field_name):
        equipment_with_additional_membership_value(
            field_name=field_name,
            value=(MembershipId("skill:bonus"),),
        )


@pytest.mark.parametrize(
    "field_name",
    ["additional_series_skill_ids", "additional_group_skill_ids"],
)
@pytest.mark.parametrize("value", ["", " ", "\t\n", " skill:bonus", "skill:bonus "])
def test_additional_memberships_reject_invalid_strings(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        equipment_with_additional_membership_value(
            field_name=field_name,
            value=(value,),
        )


@pytest.mark.parametrize(
    "field_name",
    ["additional_series_skill_ids", "additional_group_skill_ids"],
)
def test_additional_memberships_reject_duplicate_ids(field_name: str) -> None:
    with pytest.raises(ValueError, match=field_name):
        equipment_with_additional_membership_value(
            field_name=field_name,
            value=("skill:bonus", "skill:bonus"),
        )


@pytest.mark.parametrize(
    ("primary_field", "additional_field"),
    [
        ("series_skill_id", "additional_series_skill_ids"),
        ("group_skill_id", "additional_group_skill_ids"),
    ],
)
def test_additional_memberships_reject_primary_membership_duplicate(
    primary_field: str,
    additional_field: str,
) -> None:
    values = {
        primary_field: "skill:bonus",
        additional_field: ("skill:bonus",),
    }

    with pytest.raises(ValueError, match=additional_field):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=EquipmentPart.WEAPON,
            skills=(),
            slots=(),
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("assignment_field", "additional_field"),
    [
        ("allows_series_skill_assignment", "additional_series_skill_ids"),
        ("allows_group_skill_assignment", "additional_group_skill_ids"),
    ],
)
def test_additional_memberships_conflict_with_assignment_capability(
    assignment_field: str,
    additional_field: str,
) -> None:
    values = {
        assignment_field: True,
        additional_field: ("skill:bonus",),
    }

    with pytest.raises(ValueError, match=assignment_field):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=EquipmentPart.WEAPON,
            skills=(),
            slots=(),
            **values,  # type: ignore[arg-type]
        )


def test_equipment_value_semantics_include_additional_memberships() -> None:
    definition = equipment(
        additional_series_skill_ids=("skill:series-extra",),
        additional_group_skill_ids=("skill:group-extra",),
    )
    equal_definition = equipment(
        additional_series_skill_ids=("skill:series-extra",),
        additional_group_skill_ids=("skill:group-extra",),
    )

    assert definition == equal_definition
    assert hash(definition) == hash(equal_definition)
    assert definition != equipment()
    with pytest.raises(FrozenInstanceError):
        definition.additional_series_skill_ids = ()


def test_additional_membership_fields_follow_all_existing_positional_fields() -> None:
    definition = EquipmentDefinition(
        "weapon:great-sword:hope-blade",
        EquipmentPart.WEAPON,
        (),
        (),
        "skill:series-primary",
        "skill:group-primary",
        False,
        False,
        "Hope Blade",
        WeaponKind.GREAT_SWORD,
        ("skill:series-extra",),
        ("skill:group-extra",),
    )

    assert definition.display_name == "Hope Blade"
    assert definition.weapon_kind is WeaponKind.GREAT_SWORD
    assert definition.additional_series_skill_ids == ("skill:series-extra",)
    assert definition.additional_group_skill_ids == ("skill:group-extra",)


@pytest.mark.parametrize("equipment_id", ["", " ", "\t\n"])
def test_equipment_definition_rejects_empty_or_blank_equipment_id(
    equipment_id: str,
) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        equipment(equipment_id=equipment_id)


@pytest.mark.parametrize(
    "equipment_id",
    [" weapon:great-sword:hope-blade", "\tweapon:great-sword:hope-blade"],
)
def test_equipment_definition_rejects_leading_whitespace_equipment_id(
    equipment_id: str,
) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        equipment(equipment_id=equipment_id)


@pytest.mark.parametrize(
    "equipment_id",
    ["weapon:great-sword:hope-blade ", "weapon:great-sword:hope-blade\n"],
)
def test_equipment_definition_rejects_trailing_whitespace_equipment_id(
    equipment_id: str,
) -> None:
    with pytest.raises(ValueError, match="equipment_id"):
        equipment(equipment_id=equipment_id)


@pytest.mark.parametrize("equipment_id", [1, None])
def test_equipment_definition_rejects_non_str_equipment_id(
    equipment_id: object,
) -> None:
    with pytest.raises(TypeError, match="equipment_id"):
        equipment(equipment_id=equipment_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("part", ["weapon", None])
def test_equipment_definition_rejects_invalid_part(part: object) -> None:
    with pytest.raises(TypeError, match="part"):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=part,  # type: ignore[arg-type]
            skills=(skill(),),
            slots=(weapon_slot(1),),
        )


def test_equipment_definition_accepts_empty_skills() -> None:
    definition = equipment(skills=())

    assert definition.skills == ()


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
def test_equipment_definition_rejects_non_tuple_skills(skills: object) -> None:
    with pytest.raises(TypeError, match="skills"):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=EquipmentPart.WEAPON,
            skills=skills,  # type: ignore[arg-type]
            slots=(weapon_slot(1),),
        )


@pytest.mark.parametrize("invalid_skill", ["skill:attack-boost", None])
def test_equipment_definition_rejects_invalid_skill_elements(
    invalid_skill: object,
) -> None:
    with pytest.raises(TypeError, match="skills"):
        equipment(skills=(invalid_skill,))  # type: ignore[arg-type]


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
def test_equipment_definition_rejects_duplicate_skill_ids(
    skills: tuple[SkillContribution, ...],
) -> None:
    with pytest.raises(ValueError, match="skills"):
        equipment(skills=skills)


def test_equipment_definition_accepts_multiple_different_skill_ids() -> None:
    skills = (
        skill("skill:attack-boost", 1),
        skill("skill:critical-eye", 1),
    )

    definition = equipment(skills=skills)

    assert definition.skills == skills


def test_equipment_definition_accepts_empty_slots() -> None:
    definition = equipment(slots=())

    assert definition.slots == ()


def slot_generator() -> Iterator[DecorationSlot]:
    yield weapon_slot(1)


@pytest.mark.parametrize(
    "slots",
    [
        [weapon_slot(1)],
        {weapon_slot(1)},
        slot_generator(),
    ],
)
def test_equipment_definition_rejects_non_tuple_slots(slots: object) -> None:
    with pytest.raises(TypeError, match="slots"):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:hope-blade",
            part=EquipmentPart.WEAPON,
            skills=(skill(),),
            slots=slots,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("invalid_slot", ["weapon", None])
def test_equipment_definition_rejects_invalid_slot_elements(
    invalid_slot: object,
) -> None:
    with pytest.raises(TypeError, match="slots"):
        equipment(slots=(invalid_slot,))  # type: ignore[arg-type]


def test_equipment_definition_accepts_duplicate_slots_and_preserves_them() -> None:
    duplicate_slot = weapon_slot(1)
    slots = (duplicate_slot, weapon_slot(2), duplicate_slot)

    definition = equipment(slots=slots)

    assert definition.slots == slots
    assert len(definition.slots) == 3


def test_domain_package_exports_equipment_definition() -> None:
    from mhwilds_skill_sim.domain import (
        EquipmentDefinition as ExportedEquipmentDefinition,
    )

    assert ExportedEquipmentDefinition is EquipmentDefinition


def test_domain_package_keeps_existing_public_exports_with_equipment_definition() -> (
    None
):
    from mhwilds_skill_sim.domain import (
        DecorationDefinition as ExportedDecorationDefinition,
        DecorationKind as ExportedDecorationKind,
        DecorationSlot as ExportedDecorationSlot,
        EquipmentPart as ExportedEquipmentPart,
        SkillContribution as ExportedSkillContribution,
        can_place_decoration as exported_can_place_decoration,
    )

    assert ExportedDecorationDefinition is DecorationDefinition
    assert ExportedDecorationKind is DecorationKind
    assert ExportedDecorationSlot is DecorationSlot
    assert ExportedEquipmentPart is EquipmentPart
    assert ExportedSkillContribution is SkillContribution
    assert exported_can_place_decoration is can_place_decoration


def test_equipment_display_name_defaults_to_none() -> None:
    definition = EquipmentDefinition(
        "armor:head:test",
        EquipmentPart.HEAD,
        (),
        (),
    )

    assert definition.display_name is None


@pytest.mark.parametrize(
    "display_name",
    [
        "テストヘルムα",
        "Hope Helm Alpha",
        "Hope  Helm: Alpha (Test)",
        "hOPE Helm-A",
    ],
)
def test_equipment_preserves_valid_display_name_exactly(display_name: str) -> None:
    definition = equipment(display_name=display_name)

    assert definition.display_name == display_name


def test_equipment_equality_and_hash_include_display_name() -> None:
    without_name = equipment()
    with_name = equipment(display_name="Hope Helm")
    same_name = equipment(display_name="Hope Helm")

    assert with_name == same_name
    assert hash(with_name) == hash(same_name)
    assert without_name != with_name
    assert len({without_name, with_name}) == 2


def test_equipment_display_name_is_frozen() -> None:
    definition = equipment(display_name="Hope Helm")

    with pytest.raises(FrozenInstanceError):
        definition.display_name = "Other Helm"


@pytest.mark.parametrize("display_name", ["", " ", "\t\n"])
def test_equipment_rejects_empty_or_blank_display_name(display_name: str) -> None:
    with pytest.raises(ValueError, match="display_name"):
        equipment(display_name=display_name)


@pytest.mark.parametrize(
    "display_name",
    [" Hope Helm", "\tHope Helm", "Hope Helm ", "Hope Helm\n"],
)
def test_equipment_rejects_display_name_edge_whitespace(
    display_name: str,
) -> None:
    with pytest.raises(ValueError, match="display_name"):
        equipment(display_name=display_name)


@pytest.mark.parametrize("display_name", [True, False, 1, 1.5, [], object()])
def test_equipment_rejects_non_string_display_name(display_name: object) -> None:
    with pytest.raises(TypeError, match="display_name"):
        EquipmentDefinition(
            equipment_id="armor:head:test",
            part=EquipmentPart.HEAD,
            skills=(),
            slots=(),
            display_name=display_name,  # type: ignore[arg-type]
        )


def test_equipment_rejects_display_name_string_subclass() -> None:
    class DisplayName(str):
        pass

    with pytest.raises(TypeError, match="display_name"):
        equipment(display_name=DisplayName("Hope Helm"))


def test_weapon_kind_declaration_order_matches_public_contract() -> None:
    assert list(WeaponKind) == EXPECTED_WEAPON_KINDS


def test_weapon_kind_member_names_match_public_contract() -> None:
    assert list(WeaponKind.__members__) == EXPECTED_WEAPON_KIND_NAMES


def test_weapon_kind_values_match_public_contract_without_aliases() -> None:
    values = [kind.value for kind in WeaponKind]

    assert values == EXPECTED_WEAPON_KIND_VALUES
    assert len(values) == len(set(values))
    assert len(WeaponKind.__members__) == len(EXPECTED_WEAPON_KIND_VALUES)


@pytest.mark.parametrize(
    ("kind", "expected"),
    zip(EXPECTED_WEAPON_KINDS, EXPECTED_WEAPON_KIND_VALUES),
)
def test_weapon_kind_string_representation_is_exact(
    kind: WeaponKind,
    expected: str,
) -> None:
    assert str(kind) == expected


@pytest.mark.parametrize("value", ["Great-Sword", "great_sword", "gs", ""])
def test_weapon_kind_rejects_aliases_case_and_punctuation_variants(
    value: str,
) -> None:
    with pytest.raises(ValueError):
        WeaponKind(value)


def test_equipment_weapon_kind_defaults_to_none() -> None:
    definition = EquipmentDefinition(
        "weapon:great-sword:test",
        EquipmentPart.WEAPON,
        (),
        (),
    )

    assert definition.weapon_kind is None


@pytest.mark.parametrize("weapon_kind", EXPECTED_WEAPON_KINDS)
def test_weapon_equipment_accepts_every_weapon_kind(
    weapon_kind: WeaponKind,
) -> None:
    definition = equipment(weapon_kind=weapon_kind)

    assert definition.part is EquipmentPart.WEAPON
    assert definition.weapon_kind is weapon_kind


def test_weapon_equipment_may_retain_none_weapon_kind() -> None:
    definition = equipment(weapon_kind=None)

    assert definition.weapon_kind is None


@pytest.mark.parametrize("value", ["great-sword", True, 1, object()])
def test_equipment_rejects_non_weapon_kind_values(value: object) -> None:
    with pytest.raises(TypeError, match="weapon_kind"):
        EquipmentDefinition(
            equipment_id="weapon:great-sword:test",
            part=EquipmentPart.WEAPON,
            skills=(),
            slots=(),
            weapon_kind=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "part",
    [
        EquipmentPart.HEAD,
        EquipmentPart.CHEST,
        EquipmentPart.ARMS,
        EquipmentPart.WAIST,
        EquipmentPart.LEGS,
        EquipmentPart.CHARM,
    ],
)
def test_non_weapon_equipment_rejects_weapon_kind(part: EquipmentPart) -> None:
    with pytest.raises(ValueError, match="weapon_kind"):
        equipment(part=part, weapon_kind=WeaponKind.GREAT_SWORD)


def test_equipment_does_not_infer_weapon_kind_from_id() -> None:
    definition = equipment(equipment_id="mhdb:weapon:bow:4001")

    assert definition.weapon_kind is None


def test_equipment_equality_and_hash_include_weapon_kind() -> None:
    without_kind = equipment()
    with_kind = equipment(weapon_kind=WeaponKind.GREAT_SWORD)
    same_kind = equipment(weapon_kind=WeaponKind.GREAT_SWORD)

    assert with_kind == same_kind
    assert hash(with_kind) == hash(same_kind)
    assert without_kind != with_kind
    assert len({without_kind, with_kind}) == 2


def test_equipment_weapon_kind_is_frozen() -> None:
    definition = equipment(weapon_kind=WeaponKind.GREAT_SWORD)

    with pytest.raises(FrozenInstanceError):
        definition.weapon_kind = WeaponKind.BOW


def test_domain_package_exports_weapon_kind_at_required_position() -> None:
    import mhwilds_skill_sim.domain as domain_package
    from mhwilds_skill_sim.domain import WeaponKind as ExportedWeaponKind

    assert ExportedWeaponKind is WeaponKind
    skill_rank_index = domain_package.__all__.index("SkillRankDefinition")
    assert domain_package.__all__[skill_rank_index + 1] == "WeaponKind"
