"""Skill domain value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillContribution:
    skill_id: str
    level: int

    def __post_init__(self) -> None:
        if type(self.skill_id) is not str:
            raise TypeError("skill_id must be str")

        if self.skill_id == "":
            raise ValueError("skill_id must not be empty")

        if self.skill_id.strip() == "":
            raise ValueError("skill_id must not be blank")

        if self.skill_id != self.skill_id.strip():
            raise ValueError("skill_id must not have leading or trailing whitespace")

        if type(self.level) is not int:
            raise TypeError("level must be int")

        if self.level < 1:
            raise ValueError("level must be at least 1")
