"""Decoration slot domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DecorationKind(StrEnum):
    WEAPON = "weapon"
    ARMOR = "armor"


@dataclass(frozen=True, slots=True)
class DecorationSlot:
    kind: DecorationKind
    level: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DecorationKind):
            raise TypeError("kind must be DecorationKind")

        if type(self.level) is not int:
            raise TypeError("level must be int")

        if self.level < 1:
            raise ValueError("level must be at least 1")
