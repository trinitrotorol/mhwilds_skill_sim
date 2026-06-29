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


def aggregate_skill_levels(
    *,
    contributions: tuple[SkillContribution, ...],
) -> dict[str, int]:
    if type(contributions) is not tuple:
        raise TypeError("contributions must be tuple")

    aggregated: dict[str, int] = {}
    for contribution in contributions:
        if not isinstance(contribution, SkillContribution):
            raise TypeError("contributions must contain only SkillContribution")

        if contribution.skill_id not in aggregated:
            aggregated[contribution.skill_id] = 0
        aggregated[contribution.skill_id] += contribution.level

    return aggregated
