"""Skill domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SkillKind(StrEnum):
    ARMOR = "armor"
    WEAPON = "weapon"
    SERIES = "set"
    GROUP = "group"


@dataclass(frozen=True, slots=True)
class SkillRankDefinition:
    level: int
    required_pieces: int | None

    def __post_init__(self) -> None:
        if type(self.level) is not int:
            raise TypeError("level must be int")

        if self.level < 1:
            raise ValueError("level must be at least 1")

        if self.required_pieces is not None and type(self.required_pieces) is not int:
            raise TypeError("required_pieces must be int or None")

        if self.required_pieces is not None and self.required_pieces < 1:
            raise ValueError("required_pieces must be at least 1")


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    skill_id: str
    kind: SkillKind
    ranks: tuple[SkillRankDefinition, ...]

    def __post_init__(self) -> None:
        if type(self.skill_id) is not str:
            raise TypeError("skill_id must be str")

        if self.skill_id == "":
            raise ValueError("skill_id must not be empty")

        if self.skill_id.strip() == "":
            raise ValueError("skill_id must not be blank")

        if self.skill_id != self.skill_id.strip():
            raise ValueError("skill_id must not have leading or trailing whitespace")

        if not isinstance(self.kind, SkillKind):
            raise TypeError("kind must be SkillKind")

        if type(self.ranks) is not tuple:
            raise TypeError("ranks must be tuple")

        if not self.ranks:
            raise ValueError("ranks must not be empty")

        for expected_level, rank in enumerate(self.ranks, start=1):
            if not isinstance(rank, SkillRankDefinition):
                raise TypeError("ranks must contain only SkillRankDefinition")

            if rank.level != expected_level:
                raise ValueError("ranks levels must be ordered as 1, 2, ..., N")

        if self.kind in (SkillKind.ARMOR, SkillKind.WEAPON):
            if any(rank.required_pieces is not None for rank in self.ranks):
                raise ValueError(
                    "ranks for armor and weapon skills must not require pieces"
                )
            return

        required_pieces = tuple(rank.required_pieces for rank in self.ranks)
        if any(value is None for value in required_pieces):
            raise ValueError("ranks for series and group skills must require pieces")

        if any(
            current <= previous
            for previous, current in zip(required_pieces, required_pieces[1:])
        ):
            raise ValueError(
                "ranks for series and group skills must have increasing required_pieces"
            )


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
