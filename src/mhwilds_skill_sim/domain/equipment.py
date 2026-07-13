"""Equipment domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationSlot


class EquipmentPart(StrEnum):
    WEAPON = "weapon"
    HEAD = "head"
    CHEST = "chest"
    ARMS = "arms"
    WAIST = "waist"
    LEGS = "legs"
    CHARM = "charm"


class WeaponKind(StrEnum):
    BOW = "bow"
    CHARGE_BLADE = "charge-blade"
    DUAL_BLADES = "dual-blades"
    GREAT_SWORD = "great-sword"
    GUNLANCE = "gunlance"
    HAMMER = "hammer"
    HEAVY_BOWGUN = "heavy-bowgun"
    HUNTING_HORN = "hunting-horn"
    INSECT_GLAIVE = "insect-glaive"
    LANCE = "lance"
    LIGHT_BOWGUN = "light-bowgun"
    LONG_SWORD = "long-sword"
    SWITCH_AXE = "switch-axe"
    SWORD_SHIELD = "sword-shield"


def _validate_additional_skill_ids(
    *,
    field_name: str,
    skill_ids: tuple[str, ...],
) -> None:
    if type(skill_ids) is not tuple:
        raise TypeError(f"{field_name} must be tuple")

    seen_skill_ids: set[str] = set()
    for skill_id in skill_ids:
        if type(skill_id) is not str:
            raise TypeError(f"{field_name} must contain only str")

        if skill_id == "":
            raise ValueError(f"{field_name} must not contain empty IDs")

        if skill_id.strip() == "":
            raise ValueError(f"{field_name} must not contain blank IDs")

        if skill_id != skill_id.strip():
            raise ValueError(
                f"{field_name} must not contain IDs with leading or trailing whitespace"
            )

        if skill_id in seen_skill_ids:
            raise ValueError(f"{field_name} must not contain duplicate IDs")

        seen_skill_ids.add(skill_id)


@dataclass(frozen=True, slots=True)
class EquipmentDefinition:
    equipment_id: str
    part: EquipmentPart
    skills: tuple[SkillContribution, ...]
    slots: tuple[DecorationSlot, ...]
    series_skill_id: str | None = None
    group_skill_id: str | None = None
    allows_series_skill_assignment: bool = False
    allows_group_skill_assignment: bool = False
    display_name: str | None = None
    weapon_kind: WeaponKind | None = None
    additional_series_skill_ids: tuple[str, ...] = ()
    additional_group_skill_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.equipment_id) is not str:
            raise TypeError("equipment_id must be str")

        if self.equipment_id == "":
            raise ValueError("equipment_id must not be empty")

        if self.equipment_id.strip() == "":
            raise ValueError("equipment_id must not be blank")

        if self.equipment_id != self.equipment_id.strip():
            raise ValueError(
                "equipment_id must not have leading or trailing whitespace",
            )

        if not isinstance(self.part, EquipmentPart):
            raise TypeError("part must be EquipmentPart")

        if type(self.skills) is not tuple:
            raise TypeError("skills must be tuple")

        seen_skill_ids: set[str] = set()
        for skill in self.skills:
            if not isinstance(skill, SkillContribution):
                raise TypeError("skills must contain only SkillContribution")

            if skill.skill_id in seen_skill_ids:
                raise ValueError("skills must not contain duplicate skill_id")

            seen_skill_ids.add(skill.skill_id)

        if type(self.slots) is not tuple:
            raise TypeError("slots must be tuple")

        for slot in self.slots:
            if not isinstance(slot, DecorationSlot):
                raise TypeError("slots must contain only DecorationSlot")

        if self.series_skill_id is not None:
            if type(self.series_skill_id) is not str:
                raise TypeError("series_skill_id must be str or None")

            if self.series_skill_id == "":
                raise ValueError("series_skill_id must not be empty")

            if self.series_skill_id.strip() == "":
                raise ValueError("series_skill_id must not be blank")

            if self.series_skill_id != self.series_skill_id.strip():
                raise ValueError(
                    "series_skill_id must not have leading or trailing whitespace"
                )

        if self.group_skill_id is not None:
            if type(self.group_skill_id) is not str:
                raise TypeError("group_skill_id must be str or None")

            if self.group_skill_id == "":
                raise ValueError("group_skill_id must not be empty")

            if self.group_skill_id.strip() == "":
                raise ValueError("group_skill_id must not be blank")

            if self.group_skill_id != self.group_skill_id.strip():
                raise ValueError(
                    "group_skill_id must not have leading or trailing whitespace"
                )

        _validate_additional_skill_ids(
            field_name="additional_series_skill_ids",
            skill_ids=self.additional_series_skill_ids,
        )
        _validate_additional_skill_ids(
            field_name="additional_group_skill_ids",
            skill_ids=self.additional_group_skill_ids,
        )

        if self.series_skill_id in self.additional_series_skill_ids:
            raise ValueError(
                "additional_series_skill_ids must not contain series_skill_id"
            )

        if self.group_skill_id in self.additional_group_skill_ids:
            raise ValueError(
                "additional_group_skill_ids must not contain group_skill_id"
            )

        if type(self.allows_series_skill_assignment) is not bool:
            raise TypeError("allows_series_skill_assignment must be bool")

        if type(self.allows_group_skill_assignment) is not bool:
            raise TypeError("allows_group_skill_assignment must be bool")

        if self.allows_series_skill_assignment and (
            self.series_skill_id is not None or self.additional_series_skill_ids
        ):
            raise ValueError(
                "allows_series_skill_assignment requires series_skill_id to be None "
                "and additional_series_skill_ids to be empty"
            )

        if self.allows_group_skill_assignment and (
            self.group_skill_id is not None or self.additional_group_skill_ids
        ):
            raise ValueError(
                "allows_group_skill_assignment requires group_skill_id to be None "
                "and additional_group_skill_ids to be empty"
            )

        if (
            self.allows_series_skill_assignment
            and self.part is not EquipmentPart.WEAPON
        ):
            raise ValueError("allows_series_skill_assignment requires weapon equipment")

        if self.allows_group_skill_assignment and self.part is not EquipmentPart.WEAPON:
            raise ValueError("allows_group_skill_assignment requires weapon equipment")

        if self.display_name is not None:
            if type(self.display_name) is not str:
                raise TypeError("display_name must be str or None")

            if self.display_name == "":
                raise ValueError("display_name must not be empty")

            if self.display_name.strip() == "":
                raise ValueError("display_name must not be blank")

            if self.display_name != self.display_name.strip():
                raise ValueError(
                    "display_name must not have leading or trailing whitespace"
                )

        if self.weapon_kind is not None:
            if not isinstance(self.weapon_kind, WeaponKind):
                raise TypeError("weapon_kind must be WeaponKind or None")

            if self.part is not EquipmentPart.WEAPON:
                raise ValueError("weapon_kind requires weapon equipment")

    @property
    def series_skill_ids(self) -> tuple[str, ...]:
        if self.series_skill_id is None:
            return self.additional_series_skill_ids

        return (self.series_skill_id, *self.additional_series_skill_ids)

    @property
    def group_skill_ids(self) -> tuple[str, ...]:
        if self.group_skill_id is None:
            return self.additional_group_skill_ids

        return (self.group_skill_id, *self.additional_group_skill_ids)
