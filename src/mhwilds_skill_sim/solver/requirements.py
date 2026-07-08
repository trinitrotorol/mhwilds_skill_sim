"""Skill level requirement checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillRequirement:
    skill_id: str
    min_level: int

    def __post_init__(self) -> None:
        _validate_skill_id(value=self.skill_id, field_name="skill_id")
        _validate_level(value=self.min_level, field_name="min_level", minimum=1)


def skill_levels_satisfy_requirements(
    *,
    skill_levels: dict[str, int],
    requirements: tuple[SkillRequirement, ...],
) -> bool:
    if type(skill_levels) is not dict:
        raise TypeError("skill_levels must be dict")

    for skill_id, level in skill_levels.items():
        _validate_skill_id(value=skill_id, field_name="skill_levels keys")
        _validate_level(value=level, field_name="skill_levels values", minimum=0)

    if type(requirements) is not tuple:
        raise TypeError("requirements must be tuple")

    seen_skill_ids: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, SkillRequirement):
            raise TypeError("requirements must contain only SkillRequirement")

        if requirement.skill_id in seen_skill_ids:
            raise ValueError("requirements must not contain duplicate skill_id")

        seen_skill_ids.add(requirement.skill_id)

    return all(
        skill_levels.get(requirement.skill_id, 0) >= requirement.min_level
        for requirement in requirements
    )


def _validate_skill_id(*, value: object, field_name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")

    if value == "":
        raise ValueError(f"{field_name} must not be empty")

    if value.strip() == "":
        raise ValueError(f"{field_name} must not be blank")

    if value != value.strip():
        raise ValueError(f"{field_name} must not have leading or trailing whitespace")


def _validate_level(*, value: object, field_name: str, minimum: int) -> None:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be int")

    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
