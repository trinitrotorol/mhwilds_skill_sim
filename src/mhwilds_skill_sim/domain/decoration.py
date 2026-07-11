"""Decoration domain value objects."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.domain.skill import SkillContribution
from mhwilds_skill_sim.domain.slot import DecorationSlot


@dataclass(frozen=True, slots=True)
class DecorationDefinition:
    decoration_id: str
    required_slot: DecorationSlot
    skills: tuple[SkillContribution, ...]
    display_name: str | None = None

    def __post_init__(self) -> None:
        if type(self.decoration_id) is not str:
            raise TypeError("decoration_id must be str")

        if self.decoration_id == "":
            raise ValueError("decoration_id must not be empty")

        if self.decoration_id.strip() == "":
            raise ValueError("decoration_id must not be blank")

        if self.decoration_id != self.decoration_id.strip():
            raise ValueError(
                "decoration_id must not have leading or trailing whitespace",
            )

        if not isinstance(self.required_slot, DecorationSlot):
            raise TypeError("required_slot must be DecorationSlot")

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
