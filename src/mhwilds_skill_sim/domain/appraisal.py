"""Appraisal charm rule domain value objects."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationKind, DecorationSlot


def _validate_identifier(*, value: object, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")

    if value == "":
        raise ValueError(f"{field_name} must not be empty")

    if value.strip() == "":
        raise ValueError(f"{field_name} must not be blank")

    if value != value.strip():
        raise ValueError(f"{field_name} must not have leading or trailing whitespace")


@dataclass(frozen=True, slots=True)
class AppraisalCharmSkillGroupDefinition:
    group_id: str
    skills: tuple[SkillContribution, ...]

    def __post_init__(self) -> None:
        _validate_identifier(value=self.group_id, field_name="group_id")

        if type(self.skills) is not tuple:
            raise TypeError("skills must be tuple")

        if not self.skills:
            raise ValueError("skills must not be empty")

        seen_skill_ids: set[str] = set()
        for skill in self.skills:
            if not isinstance(skill, SkillContribution):
                raise TypeError("skills must contain only SkillContribution")

            if skill.skill_id in seen_skill_ids:
                raise ValueError("skills must not contain duplicate skill_id")

            seen_skill_ids.add(skill.skill_id)


@dataclass(frozen=True, slots=True)
class AppraisalCharmPatternDefinition:
    pattern_id: str
    rarity: int
    skill_group_ids: tuple[str, ...]
    slots: tuple[DecorationSlot, ...]

    def __post_init__(self) -> None:
        _validate_identifier(value=self.pattern_id, field_name="pattern_id")

        if type(self.rarity) is not int:
            raise TypeError("rarity must be int")

        if self.rarity < 1:
            raise ValueError("rarity must be at least 1")

        if type(self.skill_group_ids) is not tuple:
            raise TypeError("skill_group_ids must be tuple")

        if not 1 <= len(self.skill_group_ids) <= 3:
            raise ValueError("skill_group_ids must contain between 1 and 3 items")

        for group_id in self.skill_group_ids:
            _validate_identifier(value=group_id, field_name="skill_group_ids")

        if type(self.slots) is not tuple:
            raise TypeError("slots must be tuple")

        for slot in self.slots:
            if not isinstance(slot, DecorationSlot):
                raise TypeError("slots must contain only DecorationSlot")

        if len(self.slots) > 4:
            raise ValueError("slots must contain at most 4 items")

        weapon_slot_count = sum(
            slot.kind is DecorationKind.WEAPON for slot in self.slots
        )
        if weapon_slot_count > 1:
            raise ValueError("slots must contain at most one weapon slot")

        armor_slot_count = sum(slot.kind is DecorationKind.ARMOR for slot in self.slots)
        if armor_slot_count > 3:
            raise ValueError("slots must contain at most three armor slots")

        armor_slot_seen = False
        for slot in self.slots:
            if slot.kind is DecorationKind.ARMOR:
                armor_slot_seen = True
            elif armor_slot_seen:
                raise ValueError("slots weapon slot must appear before armor slots")
