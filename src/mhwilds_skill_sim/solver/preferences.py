"""Preferred skill values and scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillPreference:
    skill_id: str
    target_level: int

    def __post_init__(self) -> None:
        _validate_skill_id(value=self.skill_id, field_name="skill_id")
        _validate_level(value=self.target_level, field_name="target_level", minimum=1)


def calculate_skill_preference_score(
    *,
    skill_levels: dict[str, int],
    preferences: tuple[SkillPreference, ...],
) -> int:
    if type(skill_levels) is not dict:
        raise TypeError("skill_levels must be dict")

    for skill_id, level in skill_levels.items():
        _validate_skill_id(value=skill_id, field_name="skill_levels keys")
        _validate_level(value=level, field_name="skill_levels values", minimum=0)

    if type(preferences) is not tuple:
        raise TypeError("preferences must be tuple")

    seen_skill_ids: set[str] = set()
    for preference in preferences:
        if not isinstance(preference, SkillPreference):
            raise TypeError("preferences must contain only SkillPreference")

        if preference.skill_id in seen_skill_ids:
            raise ValueError("preferences must not contain duplicate skill_id")

        seen_skill_ids.add(preference.skill_id)

    return sum(
        min(skill_levels.get(preference.skill_id, 0), preference.target_level)
        for preference in preferences
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
