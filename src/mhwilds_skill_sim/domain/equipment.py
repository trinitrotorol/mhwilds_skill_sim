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

        if type(self.allows_series_skill_assignment) is not bool:
            raise TypeError("allows_series_skill_assignment must be bool")

        if type(self.allows_group_skill_assignment) is not bool:
            raise TypeError("allows_group_skill_assignment must be bool")

        if self.allows_series_skill_assignment and self.series_skill_id is not None:
            raise ValueError(
                "allows_series_skill_assignment requires series_skill_id to be None"
            )

        if self.allows_group_skill_assignment and self.group_skill_id is not None:
            raise ValueError(
                "allows_group_skill_assignment requires group_skill_id to be None"
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
